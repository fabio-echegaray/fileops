from pathlib import Path

import dask
import dask.array as da
import numpy as np

from fileops.image import ImageFile
from fileops.image import to_8bit
from fileops.image.imagemeta import MetadataImageSeries
from fileops.logger import get_logger


class LazyImageFile(ImageFile):
    log = get_logger(name='LazyImageFile')

    def __init__(self, image_path: Path, **kwargs):
        super(LazyImageFile, self).__init__(image_path, **kwargs)

    def images(self, channel='all', zstack='all', frame='all', as_8bit=False) -> dask.array.Array:
        series = [s.attrib['ID'] for s in self.all_series]
        frames = self.frames if frame == 'all' else [*frame]
        zstacks = self.zstacks if zstack == 'all' else [*zstack]
        channels = self.channels if channel == 'all' else [*channel]

        @dask.delayed
        def lazy_im(s, c, z, t):
            if s != self.series_num:
                self.series_num = s
                self._load_imageseries()
            try:
                ix = self.ix_at(c, z, t)
                img = to_8bit(self.image(ix).image) if as_8bit else self.image(ix).image

                return img[np.newaxis, np.newaxis, np.newaxis, np.newaxis, :]
            except Exception as e:
                self.log.error(e)
                return np.empty((self.width, self.height))[np.newaxis, np.newaxis, np.newaxis, np.newaxis, :]

        # get structure of first image to gather data type info
        test_img = self.image(0).image

        # Stack delayed images into one large dask.array
        arr_t = list()
        for t in frames:
            arr_c = list()
            for c in channels:
                arr_z = list()
                for z in zstacks:
                    dask_z = da.stack([
                        da.from_delayed(lazy_im(s, c, z, t),
                                        shape=(1, 1, 1, 1, *test_img.shape,),
                                        dtype=np.uint8 if as_8bit else test_img.dtype
                                        )
                        for s, _ in enumerate(series)], axis=0)
                    arr_z.append(dask_z)
                arr_c.append(da.stack(arr_z, axis=0))
            arr_t.append(da.stack(arr_c, axis=0))
        stack = da.stack(arr_t, axis=0)

        return stack

    def image_series(self, channel='all', zstack='all', frame='all', as_8bit=False) -> MetadataImageSeries:
        stack = self.images(channel=channel, zstack=zstack, frame=frame, as_8bit=as_8bit)

        return MetadataImageSeries(reader="tifffile",
                                   images=stack, pix_per_um=self.pix_per_um, um_per_pix=self.um_per_pix,
                                   frames=stack.shape[0], timestamps=stack.shape[0],
                                   time_interval=self.time_interval,
                                   channels=stack.shape[2], zstacks=stack.shape[1],
                                   width=self.width, height=self.height,
                                   series=None, intensity_ranges=None)
