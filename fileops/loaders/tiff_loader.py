import os
import io
import logging

import numpy as np
import tifffile as tf

from fileops.image.imagemeta import MetadataImageSeries

logger = logging.getLogger(__name__)


def load_tiff(file_or_path) -> MetadataImageSeries:
    if type(file_or_path) == str:
        _, img_name = os.path.split(file_or_path)
    if issubclass(type(file_or_path), io.BufferedIOBase):
        _, img_name = os.path.split(file_or_path.name)

    res = None
    with tf.TiffFile(file_or_path) as tif:
        assert len(tif.series) == 1, "Not currently handled."
        idx = tif.series[0].axes
        width = tif.series[0].shape[idx.find('X')]
        height = tif.series[0].shape[idx.find('Y')]

        if tif.is_imagej is not None:
            metadata = {}
            if tif.imagej_metadata is not None:
                metadata = tif.imagej_metadata

            dt = metadata['finterval'] if 'finterval' in metadata else None

            # asuming square pixels
            if 'XResolution' in tif.pages[0].tags:
                xr = tif.pages[0].tags['XResolution'].value
                res = float(xr[0]) / float(xr[1])  # pixels per um
                if tif.pages[0].tags['ResolutionUnit'].value == 'CENTIMETER':
                    res = res / 1e4

            images = None
            pages = tif.series[0].pages
            if len(pages) == 1:
                if ('slices' in metadata and metadata['slices'] > 1) or (
                        'frames' in metadata and metadata['frames'] > 1):
                    images = pages.asarray()
                else:
                    images = [pages.asarray()]
            elif len(pages) > 1:
                images = list()
                for i, page in enumerate(pages):
                    images.append(page.asarray())

            ax_dct = {n: k for k, n in enumerate(tif.series[0].axes)}
            shape = tif.series[0].shape
            frames = metadata['frames'] if 'frames' in metadata else 1
            ts = np.linspace(start=0, stop=frames * dt, num=frames) if dt is not None else None
            return MetadataImageSeries(reader="load_tiff",
                                       images=np.asarray(images), pix_per_um=res, um_per_pix=1. / res,
                                       um_per_z=metadata['spacing'] if 'spacing' in metadata else 1,
                                       slices=metadata['slices'] if 'slices' in metadata else 1,
                                       time_interval=dt, frames=frames, timestamps=ts.tolist(),
                                       channels=metadata['channels'] if 'channels' in metadata else 1,
                                       zstacks=shape[ax_dct['Z']] if 'Z' in ax_dct else 1,
                                       width=width, height=height, series=tif.series[0],
                                       intensity_ranges=metadata['Ranges'] if 'Ranges' in metadata else None)


def retrieve_image(image_arr, frame, channel=0, number_of_frames=1):
    nimgs = image_arr.shape[0]
    n_channels = int(nimgs / number_of_frames)
    ix = frame * n_channels + channel
    logger.debug("Retrieving frame %d of channel %d (index=%d)" % (frame, channel, ix))
    return image_arr[ix]
