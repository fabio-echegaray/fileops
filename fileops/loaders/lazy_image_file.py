import dask
import dask.array as da
import javabridge
import numpy as np
from dask import delayed

from fileops.cached import CachedImageFile
from fileops.image import to_8bit
from fileops.image.imagemeta import MetadataImageSeries
from fileops.logger import get_logger


class LazyImageFile(CachedImageFile):
    log = get_logger(name='LazyImageFile')

    def __init__(self, image_path: str, **kwargs):
        super(LazyImageFile, self).__init__(image_path, **kwargs)

    def images(self, channel='all', zstack='all', frame='all', as_8bit=False) -> dask.array.Array:
        lazy_image_array = list()
        frames = self.frames if frame == 'all' else [frame]
        zstacks = self.zstacks if zstack == 'all' else [zstack]
        channels = self.channels if channel == 'all' else [channel]

        @dask.delayed
        def lazy_img_ret(ix):
            javabridge.attach()
            img = to_8bit(self.image(ix).image) if as_8bit else self.image(ix).image
            return img[np.newaxis, np.newaxis, np.newaxis, :]

        for t in frames:
            for zs in zstacks:
                for ch in channels:
                    ix = self.ix_at(ch, zs, t)
                    # self.log.debug(f"Lazy loading image from index {ix} (c={ch}, z={zs}, and t={t}).")
                    lazy_img = lazy_img_ret(ix)
                    lazy_image_array.append(lazy_img)

        # get structure of first image to gather data type info
        test_img = self.image(0).image

        dask_arrays = [
            da.from_delayed(delayed_reader, shape=(len(frames), len(zstacks), len(channels), *test_img.shape),
                            dtype=np.uint8 if as_8bit else test_img.dtype)
            for delayed_reader in lazy_image_array
        ]
        # Stack delayed images into one large dask.array
        stack = da.stack(dask_arrays, axis=0)

        return stack

    def image_series(self, channel='all', zstack='all', frame='all', as_8bit=False) -> MetadataImageSeries:
        stack = self.images(channel=channel, zstack=zstack, frame=frame, as_8bit=as_8bit)

        return MetadataImageSeries(images=stack, pix_per_um=self.pix_per_um, um_per_pix=self.um_per_pix,
                                   frames=stack.shape[0], timestamps=stack.shape[0],
                                   time_interval=None,  # self.time_interval,
                                   channels=stack.shape[2], zstacks=stack.shape[1],
                                   width=self.width, height=self.height,
                                   series=None, intensity_ranges=None)
