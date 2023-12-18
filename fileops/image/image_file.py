from pathlib import Path

import numpy as np

from fileops.image import to_8bit
from fileops.image._base import ImageFileBase
from fileops.image.exceptions import FrameNotFoundError
from fileops.image.imagemeta import MetadataImageSeries, MetadataImage
from fileops.logger import get_logger


class ImageFile(ImageFileBase):
    log = get_logger(name='ImageFile')

    def __init__(self, image_path: Path, image_series=0, failover_dt=None, failover_mag=None, **kwargs):
        self.image_path = image_path
        self.base_path = self.image_path.parent
        self.metadata_path = None
        self.log.debug(f"Image file path is {self.image_path.as_posix().encode('ascii')}.")

        self._series = image_series
        self._info = None
        self._init_data_structures()

        self._load_imageseries()

        self._failover_dt = self._failover_mag = None
        self._fix_defaults(failover_dt=failover_dt, failover_mag=failover_mag)

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

    def _fix_defaults(self, failover_dt=None, failover_mag=None):
        if not self.timestamps and self.frames:
            if failover_dt is None:
                self._failover_dt = 1
                self.log.warning(f"Empty array of timestamps and no failover_dt parameter provided. Resorting to 1[s].")
            else:
                self.log.warning(f"Overriding sampling time with {failover_dt}[s]")
                self._failover_dt = float(failover_dt)

            self.log.warning(f"Overriding sampling time with {self._failover_dt}[s]")
            self.time_interval = self._failover_dt
            self.timestamps = [self._failover_dt * f for f in self.frames]
        else:
            if failover_dt is not None:
                self._failover_dt = float(failover_dt)
                self.log.warning(
                    f"Timesamps were constructed but overriding regardless with a sampling time of {failover_dt}[s]")
                self.time_interval = self._failover_dt
                self.timestamps = [self._failover_dt * f for f in self.frames]

        if failover_mag is not None:
            self.log.warning(f"Overriding magnification parameter with {failover_mag}")
            self._failover_mag = failover_mag
            self.magnification = failover_mag

    @property
    def series(self):
        return self.all_series[self._series]

    def plane_at(self, c, z, t):
        return f"c{c:0{len(str(self.n_channels))}d}z{z:0{len(str(self.n_zstacks))}d}t{t:0{len(str(self.n_frames))}d}"

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
        return MetadataImageSeries(images=images, pix_per_um=self.pix_per_um, um_per_pix=self.um_per_pix,
                                   frames=len(frames), timestamps=len(frames),
                                   time_interval=None,  # self.time_interval,
                                   channels=len(channels), zstacks=len(zstacks),
                                   width=self.width, height=self.height,
                                   series=None, intensity_ranges=None)

    def z_projection(self, frame: int, channel: int, projection='max', as_8bit=False):
        self.log.debug(f"executing z-{projection}-projection.")

        images = list()

        for zs in range(self.n_zstacks):
            try:
                if self.ix_at(channel, zs, frame) is not None:
                    plane = self.plane_at(channel, zs, frame)
                    img = self._image(plane).image
                    images.append(to_8bit(img) if as_8bit else img)
            except FrameNotFoundError as e:
                self.log.error(f"image at t={frame} c={channel} z={zs} not found in file.")

        if len(images) == 0:
            self.log.error(f"not able to make a z-projection at t={frame} c={channel}.")
            raise FrameNotFoundError

        im_vol = np.asarray(images).reshape((len(images), *images[-1].shape))
        im_proj = np.max(im_vol, axis=0)
        return MetadataImage(reader='MaxProj',
                             image=im_proj,
                             pix_per_um=self.pix_per_um, um_per_pix=self.um_per_pix,
                             frame=frame, timestamp=None, time_interval=None,
                             channel=channel, z=None,
                             width=self.width, height=self.height,
                             intensity_range=[np.min(im_proj), np.max(im_proj)])
