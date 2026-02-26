from datetime import datetime
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd
from ome_types import OME

from fileops.image._ome import ome_info
from fileops.image.image_file import ImageFile
from fileops.logger import get_logger


class OMEImageFile(ImageFile):
    ome_ns = {'ome': 'http://www.openmicroscopy.org/Schemas/OME/2016-06'}
    md_ome: OME | None = None
    log = get_logger(name='OMEImageFile')

    def __init__(self, image_path: Path, image_series: int = 0, **kwargs):
        super(OMEImageFile, self).__init__(image_path, **kwargs)

    def _load_imageseries(self, series: int):
        if self.all_series is None or len(self.all_series) < 1:
            return
        self._series = series

        self.n_channels = self.md_ome.image_size_c
        self.n_zstacks = self.md_ome.image_size_z if self.md_ome.image_size_z is not None else 1
        self.n_frames = self.md_ome.image_size_t if self.md_ome.image_size_t is not None else 1
        self.channels = set(range(self.n_channels))
        self.zstacks = list(range(self.n_zstacks))
        # self.z_position = np.array([p.get('PositionZ') for p in self.all_planes]).astype(float)
        self.frames = list(range(self.n_frames))
        self._md_n_zstacks = self.n_zstacks
        self._md_n_frames = self.n_frames
        self._md_n_channels = self.n_channels
        self.um_per_pix = self.md_ome.pixel_size_x if self.md_ome.pixel_size_x == self.md_ome.pixel_size_y else np.nan
        self.pix_per_um = 1. / self.um_per_pix
        self.width = self.md_ome.image_size_x
        self.height = self.md_ome.image_size_y
        self.um_per_z = self.md_ome.pixel_size_z

        # obj = self.images_md.find('ObjectiveSettings', self.ome_ns)
        # obj_id = obj.get('ID') if obj else None
        # objective = self.md_ome.find(f'Instrument/Objective[@ID="{obj_id}"]', self.ome_ns) if obj else None
        # self.magnification = int(float(objective.get('NominalMagnification'))) if objective else None

        if self.n_frames > 1:
            ts_diff = self.md_ome.timelapse_interval
            self.time_interval = ts_diff.seconds + ts_diff.microseconds / 10 ** 6
            assert self.time_interval >= 0
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

    @property
    def info(self) -> pd.DataFrame:
        if self.all_series is None:
            return
        fname_stat = Path(self.image_path).stat()
        fcreated = datetime.fromtimestamp(fname_stat.st_ctime).strftime("%a %b/%d/%Y, %H:%M:%S")
        fmodified = datetime.fromtimestamp(fname_stat.st_mtime).strftime("%a %b/%d/%Y, %H:%M:%S")
        series_info = list()

        snfo = list(ome_info(self.md_ome))

        for s in snfo:
            s.update({
                'filename':                          self.image_path.name,
                'folder':                            self.image_path.parent.as_posix(),
                # 'series_id':                       int(_series.split(":")[1]),
                'change (Unix), creation (Windows)': fcreated,
                'most recent modification':          fmodified,
            })
        series_info.extend(snfo)

        out = pd.DataFrame(series_info)
        return out
