import os

import pandas as pd

from fileops import logger
from fileops.cached import CachedImageFile
from fileops.loaders import load_tiff

log = logger.get_logger(__name__)


def image_list(folder: str):
    folder_list = list()
    for root, directories, filenames in os.walk(folder):
        common = os.path.relpath(root, start=folder)
        for file in filenames:
            joinf = os.path.abspath(os.path.join(root, file))
            ext = joinf[-4:]
            name = os.path.basename(joinf)
            if os.path.isfile(joinf) and ext == '.tif':
                tiffmd = load_tiff(joinf)
                folder_list.append({
                    'name':            name,
                    'folder':          common,
                    'resolution':      tiffmd.pix_per_um,
                    'meta_img_shape':  tiffmd.images.shape,
                    'width':           tiffmd.width,
                    'height':          tiffmd.height,
                    'time_interval':   tiffmd.time_interval,
                    'number_frames':   tiffmd.frames,
                    'number_channels': tiffmd.channels,
                })
    df = pd.DataFrame(folder_list)
    df.to_csv(os.path.join(folder, os.path.basename(folder) + "summary.csv"))
    return df


class ImageMixin:
    log = None

    def __init__(self, filename, **kwargs):
        self.log.debug("ImageMixin init.")
        self.filename = filename

        self._c = CachedImageFile(filename, cache_results=False)

        # self.log.info(f"Image retrieved has axes format {self.series.axes}")
        super().__init__(**kwargs)

    def _load_tiff(self):
        self._f = open(self.filename, 'rb')
        im = load_tiff(self._f)
        self.images = im.images
        self.series = im.series
        self.pix_per_um = im.pix_per_um
        self.um_per_pix = im.um_per_pix
        self.dt = im.time_interval
        self.frames = im.frames
        self.timestamps = None
        self.stacks = im.zstacks
        self.channels = im.channels
        self.width = im.width
        self.height = im.height
        self._image_file = os.path.basename(self.filename)
        self._image_path = os.path.dirname(self.filename)

    def __del__(self):
        if hasattr(self, '_f') and self._f is not None:
            self._f.close()

    def max_projection(self, frame=None, channel=None):
        if frame is None:
            pass
        elif self.series.axes == 'TCYX':
            if channel is None:
                return self.series.asarray()[frame, :, :, :]
            else:
                return self.series.asarray()[frame, channel, :, :]
