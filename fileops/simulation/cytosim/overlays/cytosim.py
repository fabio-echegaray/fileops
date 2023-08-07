from pathlib import Path

import numpy as np

from fileops.image import MetadataImage
from movierender.overlays import Overlay


class SimulationGrid(Overlay):
    def __init__(self, simulations_folder: Path, **kwargs):
        super().__init__(**kwargs)

    def plot(self, ax=None, **kwargs):
        # self.log.debug('Plotting histogram of image.')
        if ax is None:
            ax = self.ax
        assert ax is not None, "No axes found to plot overlay."

        r = self._renderer
        ix = r.image.ix_at(c=self.hist_channel, z=self.hist_zstack, t=r.frame - 1)
        mimg = r.image.image(ix)
        img = mimg.image if (type(mimg) == MetadataImage and mimg.image is not None) else np.zeros(0)
        ax.hist(img.flatten(), bins=256, color='r', alpha=0.5)

        mimg = r.image_pipeline[0]()
        img = mimg.image if (type(mimg) == MetadataImage and mimg.image is not None) else np.zeros(0)
        ax.hist(img.flatten(), bins=256, color='b', alpha=0.5)

        # hist, bins = np.histogram(img.flatten(), 256, [0, 256])
        # cdf = hist.cumsum()
        # cdf_normalized = cdf * float(hist.max()) / cdf.max()
        # ax.plot(cdf_normalized, color='b')

        # ax.set_xlim([0, 256])
        ax.legend(('original', 'transformed'), loc='upper left')
