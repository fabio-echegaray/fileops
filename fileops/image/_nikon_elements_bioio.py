import re
from itertools import product
from pathlib import Path
from typing import Tuple

import bioio_base
import bioio_base.exceptions
import bioio_nd2
import numpy as np
from bioio import BioImage
from bioio_base.standard_metadata import StandardMetadata
from ome_types import OME

from fileops.image.exceptions import FrameNotFoundError
from fileops.image.image_file import ImageFile
from fileops.image.imagemeta import MetadataImage
from fileops.logger import get_logger


class BioioNikonImageFile(ImageFile):
    log = get_logger(name='BioioNikonImageFile')

    def __init__(self, image_path: Path, image_series: int = 0, **kwargs):
        super(BioioNikonImageFile, self).__init__(image_path, **kwargs)
        self.md, self.md_ome = self._get_metadata()
        self.all_series = self._rdr.scenes
        self.instrument_md = self.md_ome.instruments
        self.objectives_md = self.instrument_md[0].objectives
        self.log.info(f"All series: {self._rdr.scenes}.")

        self._load_imageseries(image_series)

        self._fix_defaults(override_dt=self._override_dt)

    @staticmethod
    def has_valid_format(path: Path):
        try:
            nd2_img = BioImage(path, reader=bioio_nd2.Reader)
            assert len(nd2_img.channel_names) > 0
            del nd2_img
        except bioio_base.exceptions.UnsupportedFileFormatError:
            return False

        return True

    def _load_imageseries(self, series: int):
        if not self.all_series:
            return
        self._series = series
        self._rdr.set_scene(self._series)

        self.n_channels = self.md.image_size_c
        self.n_zstacks = self.md.image_size_z
        self.n_frames = self.md.image_size_t if self.md.image_size_t is not None else 1
        self.channels = set(range(self.n_channels))
        self.zstacks = list(range(self.n_zstacks))
        # self.z_position = np.array([p.get('PositionZ') for p in self.all_planes]).astype(float)
        self.frames = list(range(self.n_frames))
        self._md_n_zstacks = self.n_zstacks
        self._md_n_frames = self.n_frames
        self._md_n_channels = self.n_channels
        self.um_per_pix = self.md.pixel_size_x if self.md.pixel_size_x == self.md.pixel_size_y else np.nan
        self.pix_per_um = 1. / self.um_per_pix
        self.width = self.md.image_size_x
        self.height = self.md.image_size_y
        self.um_per_z = self.md.pixel_size_z

        # obj = self.images_md.find('ObjectiveSettings', self.ome_ns)
        # obj_id = obj.get('ID') if obj else None
        # objective = self.md.find(f'Instrument/Objective[@ID="{obj_id}"]', self.ome_ns) if obj else None
        # self.magnification = int(float(objective.get('NominalMagnification'))) if objective else None

        if self.n_frames > 1:
            ts_diff = self.md.timelapse_interval
            self.time_interval = ts_diff.seconds + ts_diff.microseconds / 10 ** 6
            self.timestamps = list(np.linspace(0, self.n_frames * self.time_interval, num=self.n_frames + 1))

        # build dictionary where the keys are combinations of c z t and values are the index
        self.all_planes_md_dict = {f"c{int(c):0{len(str(self._md_n_channels))}d}"
                                   f"z{int(z):0{len(str(self._md_n_zstacks))}d}"
                                   f"t{int(t):0{len(str(self._md_n_frames))}d}": i  # (c, z, t)
                                   for i, (t, c, z) in enumerate(product(self.frames, self.channels, self.zstacks))}

        self.all_planes = [f"c{int(c):0{len(str(self._md_n_channels))}d}"
                           f"z{int(z):0{len(str(self._md_n_zstacks))}d}"
                           f"t{int(t):0{len(str(self._md_n_frames))}d}"
                           for t, c, z in product(self.frames, self.channels, self.zstacks)]

        self.log.info(f"Image series {self._series} loaded. "
                      f"Image size (WxH)=({self.width:d}x{self.height:d}); "
                      f"calibration is {self.pix_per_um:0.3f} pix/um and {self.um_per_z:0.3f} um/z-step; "
                      f"movie has {len(self.frames)} frames, {self.n_channels} channels, {self.n_zstacks} z-stacks and "
                      f"{len(self.all_planes_md_dict)} image planes in total.")

    def ix_at(self, c, z, t):
        czt_str = self.plane_at(c, z, t)
        if czt_str in self.all_planes_md_dict:
            return self.all_planes_md_dict[czt_str]
        self.log.warning(f"No index found for c={c}, z={z}, and t={t}.")
        return None

    def _image(self, plane, row=0, col=0, fid=0) -> MetadataImage:
        rgx = re.search(r'^c([0-9]*)z([0-9]*)t([0-9]*)$', plane)
        if rgx is None:
            raise FrameNotFoundError

        c, z, t = rgx.groups()
        c, z, t = int(c), int(z), int(t)
        # self.log.debug(f'retrieving image id={plane_ix} c={c:d} z={z:d} t={t:d}')

        # obtain 5D TCZYX xarray data array backed by dask array to then fetch the required slice
        dask_array = self._rdr.get_image_dask_data("TCZYX")
        image = dask_array[t, c, z, :, :].compute()

        return MetadataImage(reader='BioIO',
                             image=image,
                             pix_per_um=1. / self.um_per_pix, um_per_pix=self.um_per_pix,
                             time_interval=None,
                             timestamp=self.time_interval,
                             frame=int(t), channel=int(c), z=int(z), width=self.width, height=self.height,
                             intensity_range=[np.min(image), np.max(image)])

    def _get_metadata(self) -> Tuple[StandardMetadata, OME]:
        nd2_img = BioImage(self.image_path.as_posix(), reader=bioio_nd2.Reader)
        md = nd2_img.standard_metadata
        md_ome = nd2_img.ome_metadata
        self._rdr = nd2_img
        # del nd2_img

        return md, md_ome
