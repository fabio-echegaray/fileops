import re
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import tifffile as tf
from pycromanager import Core, Studio

from fileops.image import MicroManagerSingleImageStack
from fileops.image._mmanager_metadata import MetadataVersion10Mixin
from fileops.image.exceptions import FrameNotFoundError
from fileops.image.image_file import ImageFile
from fileops.image.imagemeta import MetadataImage
from fileops.logger import get_logger


class PycroManagerSingleImageStack(MicroManagerSingleImageStack):
    log = get_logger(name='PycroManagerSingleImageStack')

    def __init__(self, image_path: Path, **kwargs):
        self.mmc = None
        self.mm = None
        self.mm_store = None
        self.mm_cb = None

        super(PycroManagerSingleImageStack, self).__init__(image_path, **kwargs)

    def _init_mmc(self):
        if self.mmc is None:
            self.mmc = Core()
            self.mm = Studio(debug=True)
            self.mm_store = self.mm.data().load_data(self.image_path.as_posix(), True)
            self.mm_cb = self.mm.data().get_coords_builder()

    def _image(self, plane, row=0, col=0, fid=0) -> MetadataImage:
        rgx = re.search(r'^c([0-9]*)z([0-9]*)t([0-9]*)$', plane)
        if rgx is None:
            raise FrameNotFoundError

        c, z, t = rgx.groups()
        c, z, t = int(c), int(z), int(t)

        self._init_mmc()

        img = self.mm_store.get_image(self.mm_cb.t(t).p(0).c(c).z(z).build())
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
