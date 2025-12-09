from pathlib import Path

import numpy as np

from fileops.image import to_8bit
from fileops.image._base import ImageFileBase
from fileops.image.imagemeta import MetadataImageSeries, MetadataImage
from fileops.image.ops import z_projection
from fileops.logger import get_logger


class ImageFile(ImageFileBase):
    log = get_logger(name='ImageFile')

    def __init__(self, image_path: Path, image_series: int = 0, override_dt=None, **kwargs):
        self.image_path = image_path
        self.base_path = self.image_path.parent
        self.metadata_path = None
        self.log.debug(f"Image file path is {self.image_path.as_posix().encode('ascii')}.")

        self._info = None
        self._init_data_structures()

        self._load_imageseries(image_series)

        self._fix_defaults(override_dt=override_dt)

        super().__init__()

    def _init_data_structures(self):
        self.all_series = set()
        self.instrument_md = set()
        self.objectives_md = set()
        self.md = dict()
        self.images_md = dict()
        self.planes_md = dict()
        self.all_planes = list()
        self.all_planes_md_dict = dict()
        self.timestamps = list()
        self.positions = set()
        self.channels = set()
        self.zstacks = list()
        self.zstacks_um = list()
        self.frames = list()
        self.files = list()

    def _fix_defaults(self, override_dt=None):
        if not self.timestamps and self.frames:
            if override_dt is None:
                self._override_dt = 1
                self.log.warning(f"Empty array of timestamps and no override_dt parameter provided. Resorting to 1[s].")
            else:
                self.log.warning(f"Overriding sampling time with {override_dt}[s]")
                self._override_dt = float(override_dt)

            self.log.warning(f"Overriding sampling time with {self._override_dt}[s]")
            self.time_interval = self._override_dt
            self.timestamps = [self._override_dt * f for f in self.frames]
        else:
            if override_dt is not None:
                self._override_dt = float(override_dt)
                self.log.warning(
                    f"Timesamps were constructed but overriding regardless with a sampling time of {override_dt}[s]")
                self.time_interval = self._override_dt
                self.timestamps = [self._override_dt * f for f in self.frames]

    @property
    def series(self):
        if len(self.all_series) == 0:
            return 0
        else:
            __series = sorted(self.all_series)
            return __series[self._series]

    @series.setter
    def series(self, s: int):
        self._load_imageseries(s)

    def plane_at(self, c, z, t):
        return (f"c{int(c):0{len(str(self._md_n_channels))}d}"
                f"z{int(z):0{len(str(self._md_n_zstacks))}d}"
                f"t{int(t):0{len(str(self._md_n_frames))}d}")

    def ix_at(self, c, z, t):
        czt_str = self.plane_at(c, z, t)
        if czt_str in self.all_planes_md_dict:
            return self.all_planes_md_dict[czt_str]
        self.log.warning(f"No index found for c={c}, z={z}, and t={t}.")

    def image(self, *args, **kwargs) -> MetadataImage:
        if len(args) == 1 and isinstance(args[0], int):
            ix = args[0]
            plane = self.all_planes[ix]
            return self._image(plane, row=0, col=0, fid=0)

    def image_series(self, channel='all', zstack='all', frame='all', as_8bit=False) -> MetadataImageSeries:
        images = list()
        frames = self.frames if frame == 'all' else [frame]
        zstacks = self.zstacks if zstack == 'all' else [zstack]
        channels = self.channels if channel == 'all' else [channel]

        for t in frames:
            for zs in zstacks:
                for ch in channels:
                    ix = self.ix_at(ch, zs, t)
                    plane = self.all_planes[ix]
                    img = self._image(plane).image
                    images.append(to_8bit(img) if as_8bit else img)
        images = np.asarray(images).reshape((len(frames), len(zstacks), len(channels), *images[-1].shape))
        return MetadataImageSeries(reader="ImageFile",
                                   images=images, pix_per_um=self.pix_per_um, um_per_pix=self.um_per_pix,
                                   frames=len(frames), timestamps=len(frames),
                                   time_interval=None,  # self.time_interval,
                                   channels=len(channels),
                                   zstacks=len(zstacks), um_per_z=self.um_per_z,
                                   width=self.width, height=self.height,
                                   series=None, intensity_ranges=None,
                                   axes=["channel", "z", "time"])

    def z_projection(self, frame: int, channel: int, projection='max', as_8bit=False):
        return z_projection(self, frame, channel, projection=projection, as_8bit=as_8bit)

    def _load_imageseries(self, series: int):
        pass
