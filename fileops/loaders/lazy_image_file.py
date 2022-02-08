import dask
import dask.array as da
import javabridge
import numpy as np

from fileops.cached import CachedImageFile
from fileops.image import to_8bit
from fileops.image.imagemeta import MetadataImageSeries
from fileops.logger import get_logger


class LazyImageFile(CachedImageFile):
    log = get_logger(name='LazyImageFile')

    def __init__(self, image_path: str, **kwargs):
        super(LazyImageFile, self).__init__(image_path, **kwargs)

    def images(self, channel='all', zstack='all', frame='all', as_8bit=False) -> dask.array.Array:
        frames = self.frames if frame == 'all' else [*frame]
        zstacks = self.zstacks if zstack == 'all' else [*zstack]
        channels = self.channels if channel == 'all' else [*channel]

        @dask.delayed
        def lazy_im(c, z, t):
            try:
                ix = self.ix_at(c, z, t)
                img = to_8bit(self.image(ix).image) if as_8bit else self.image(ix).image

                return img[np.newaxis, np.newaxis, np.newaxis, :]
            except Exception as e:
                self.log.error(e)
                return np.empty((self.width, self.height))[np.newaxis, np.newaxis, np.newaxis, :]

        # get structure of first image to gather data type info
        test_img = self.image(0).image

        # Stack delayed images into one large dask.array
        arr_t = list()
        for t in frames:
            arr_c = list()
            for c in channels:
                dask_c = da.stack([
                    da.from_delayed(lazy_im(c, z, t),
                                    shape=(1, 1, 1, *test_img.shape,),
                                    dtype=np.uint8 if as_8bit else test_img.dtype
                                    )
                    for z in zstacks
                ], axis=0)
                arr_c.append(dask_c)
            arr_t.append(da.stack(arr_c, axis=0))
        stack = da.stack(arr_t, axis=0)

        return stack

    def image_series(self, channel='all', zstack='all', frame='all', as_8bit=False) -> MetadataImageSeries:
        stack = self.images(channel=channel, zstack=zstack, frame=frame, as_8bit=as_8bit)

        return MetadataImageSeries(images=stack, pix_per_um=self.pix_per_um, um_per_pix=self.um_per_pix,
                                   frames=stack.shape[0], timestamps=stack.shape[0],
                                   time_interval=self.time_interval,
                                   channels=stack.shape[2], zstacks=stack.shape[1],
                                   width=self.width, height=self.height,
                                   series=None, intensity_ranges=None)
