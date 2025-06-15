import atexit
import numbers
import re
from pathlib import Path

import numpy as np
import pycromanager
import zmq
from pycromanager import Core, Studio
from pyjavaz.bridge import _DataSocket, Bridge

from fileops.image import MicroManagerSingleImageStack
from fileops.image.exceptions import FrameNotFoundError
from fileops.image.imagemeta import MetadataImage
from fileops.logger import get_logger


class MMCoreException(BaseException):
    pass


class PycroManagerSingleImageStack(MicroManagerSingleImageStack):
    log = get_logger(name='PycroManagerSingleImageStack')

    def __init__(self, image_path: Path, raise_pycromanager_exception=False, **kwargs):
        self.mmc = None
        self.mm = None
        self.mm_store = None
        self.mm_cb = None
        self._fail_pycromanager = False
        self._raise_pycromanager_exception = raise_pycromanager_exception

        super(PycroManagerSingleImageStack, self).__init__(image_path, **kwargs)

        if self.n_positions > 1:
            raise IndexError(f"Only one position is allowed in this class, found {self.n_positions}.")
        elif self.n_positions == 1:
            try:
                position = self.positions.pop()
            except IndexError:
                self.position = 0
            if type(position) is str:
                if position == "Default":
                    self.position = 0
                else:
                    # expected string of format Text+<num> e.g. Pos0, Pos_2, Series_5 etc.
                    rgx = re.search(r'[a-zA-Z]*([0-9]+)', position)
                    self.position = int(rgx.groups()[0]) if rgx else None
            elif isinstance(position, numbers.Number):
                self.position = int(position)
            else:
                raise IndexError(f"Position is badly specified.")

        else:
            self.position = None

        self._fix_defaults(failover_dt=kwargs.get("failover_dt"), failover_mag=kwargs.get("failover_mag"))

    def _test_mmc_port(self):
        # test if port to Micro-Manager is open
        debug_socket = True
        socket = _DataSocket(
            zmq.Context.instance(),
            Bridge.DEFAULT_PORT,
            zmq.REQ,
            debug=debug_socket,
            ip_address="127.0.0.1",
        )
        socket.send({"command": "connect", "debug": debug_socket})
        reply_json = socket.receive(timeout=Bridge.DEFAULT_TIMEOUT)
        socket.close()
        if reply_json is None:
            self._fail_pycromanager = True
            atexit.unregister(pycromanager.stop_headless)
            raise MMCoreException(f"Port {Bridge.DEFAULT_PORT} is not open in Micro-Manager.")

    def _init_mmc(self):
        self._test_mmc_port()
        if self.mmc is None and not self._fail_pycromanager:
            try:
                self.mmc = Core(debug=True)
                self.mm = Studio(debug=True)
                self.mm_store = self.mm.data().load_data(self.image_path.as_posix(), True)
                self.mm_cb = self.mm.data().get_coords_builder()
            except Exception as e:
                self._fail_pycromanager = True
                atexit.unregister(pycromanager.stop_headless)
                raise MMCoreException(e)

    def _image(self, plane, row=0, col=0, fid=0) -> MetadataImage:
        rgx = re.search(r'^c([0-9]*)z([0-9]*)t([0-9]*)$', plane)
        if rgx is None:
            raise FrameNotFoundError

        c, z, t = rgx.groups()
        c, z, t = int(c), int(z), int(t)

        if not self._fail_pycromanager:
            try:
                self._init_mmc()
            except MMCoreException as e:
                if self._raise_pycromanager_exception:
                    raise e
                else:
                    return super()._image(plane, row=0, col=0, fid=0)
        else:
            if self._raise_pycromanager_exception:
                raise MMCoreException("Micro-Manager server is not on.")
            return super()._image(plane, row=0, col=0, fid=0)

        img = self.mm_store.get_image(self.mm_cb.t(t).p(self.position).c(c).z(z).build())
        if img is not None:
            image = np.reshape(img.get_raw_pixels(), newshape=[img.get_height(), img.get_width()])
        else:
            raise FrameNotFoundError

        return MetadataImage(reader='MicroManagerStack',
                             image=image,
                             pix_per_um=self.pix_per_um, um_per_pix=self.um_per_pix,
                             time_interval=None,
                             timestamp=self.timestamps[t],
                             frame=t, channel=c, z=z, width=self.width, height=self.height,
                             intensity_range=[np.min(image), np.max(image)])
