from pathlib import Path

import numpy as np

from fileops.image import to_8bit
from fileops.image._base import ImageFileBase
from fileops.image._shared_zproj_state_mixin import SharedStateZProjectionMixin
from fileops.image.imagemeta import MetadataImageSeries, MetadataImage
from fileops.image.ops import ImageProcessor
from fileops.logger import get_logger


class ImageFile(ImageFileBase, SharedStateZProjectionMixin):
    log = get_logger(name='ImageFile')

    def __init__(self, image_path: Path, image_series: int = 0, override_dt=None, **kwargs):
        """
        Constructor of the base class
        The idea for derived classes is that this method should be called only after all metadata has been fully loaded.
        """
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
        self.all_series = set() if self.all_series is None else self.all_series
        self.instrument_md = set() if self.instrument_md is None else self.instrument_md
        self.objectives_md = set() if self.objectives_md is None else self.objectives_md
        self.md = dict() if self.md is None else self.md
        self.images_md = dict() if self.images_md is None else self.images_md
        self.planes_md = dict() if self.planes_md is None else self.planes_md
        self.all_planes = list() if self.all_planes is None else self.all_planes
        self.all_planes_md_dict = dict() if self.all_planes_md_dict is None else self.all_planes_md_dict
        self.timestamps = list() if self.timestamps is None else self.timestamps
        self.positions = set() if self.positions is None else self.positions
        self.channels = set() if self.channels is None else self.channels
        self.zstacks = list() if self.zstacks is None else self.zstacks
        self.zstacks_um = list() if self.zstacks_um is None else self.zstacks_um
        self.frames = list() if self.frames is None else self.frames
        self.files = list() if self.files is None else self.files

    def _fix_defaults(self, override_dt=None):
        if not self.timestamps and self.frames:
            if override_dt is None:
                self._override_dt = 1
                self.log.warning(f"Empty array of timestamps and no override_dt parameter provided. Resorting to 1[s].")
            else:
                self.log.warning(f"Overriding sampling time with {override_dt}[s]")
                self._override_dt = float(override_dt)

            self.log.debug(f"Internal _override_dt attribute is {self._override_dt}[s]")
            self.time_interval = self._override_dt
            self.timestamps = [self._override_dt * f for f in self.frames]
        else:
            if override_dt is not None:
                self._override_dt = float(override_dt)
                self.log.warning(
                    f"Timesamps were constructed but overriding regardless with a sampling time of {override_dt}[s]")
                self.time_interval = self._override_dt
                self.timestamps = [self._override_dt * f for f in self.frames]

    def add_processor(self, processor: ImageProcessor):
        processor.on_added(self)
        self.processing_deque.appendleft(processor)

    @property
    def series(self) -> int | str | dict:
        if self.all_series is None or len(self.all_series) == 0:
            return 0
        else:
            __series = sorted(self.all_series)
            return __series[self._series]

    @series.setter
    def series(self, s: int):
        self._load_imageseries(s)

    def plane_at(self, c, z, t):
        return (f"c{int(c):0{len(str(self.n_channels))}d}"
                f"z{int(z):0{len(str(self.n_zstacks))}d}"
                f"t{int(t):0{len(str(self.n_frames))}d}")

    def ix_at(self, c, z, t):
        czt_str = self.plane_at(c, z, t)
        if czt_str in self.all_planes_md_dict:
            return self.all_planes_md_dict[czt_str]
        self.log.warning(f"No index found for c={c}, z={z}, and t={t}.")
        return None

    def image(self, *args, **kwargs) -> MetadataImage | None:
        if len(args) == 1 and isinstance(args[0], int):
            ix = args[0]
            if 0 <= ix < len(self.all_planes):
                plane = self.all_planes[ix]
                return self._image(plane, row=0, col=0, fid=0)
        return None

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

    def z_projection(self, frame: int, channel: int, projection='max', z_subset=None, as_8bit=False):
        return z_projection(self, frame, channel, projection=projection, z_subset=z_subset, as_8bit=as_8bit)

    def _load_imageseries(self, series: int):
        if self.pix_per_um is None or self.width == 0 or self.height == 0:
            return
        self.log.info(f"Image series {self._series} loaded. "
                      f"Image size (WxH)=({self.width:d}x{self.height:d}); "
                      f"calibration is {self.pix_per_um:0.3f} pix/um and {self.um_per_z:0.3f} um/z-step; "
                      f"movie has {len(self.frames)} frames, {self.n_channels} channels, {self.n_zstacks} z-stacks and "
                      f"{len(self.all_planes_md_dict)} image planes in total.")
