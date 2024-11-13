import io
import logging
import os

import numpy as np
import tifffile as tf

from fileops.image.imagemeta import MetadataImageSeries, MetadataImage

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

            # assuming square pixels
            if 'XResolution' in tif.pages[0].tags:
                xr = tif.pages[0].tags['XResolution'].value
                res = float(xr[0]) / float(xr[1])  # pixels per um
                if tif.pages[0].tags['ResolutionUnit'].value == 'CENTIMETER':
                    res = res / 1e4

            images = None
            if len(tif.pages) == 1:
                if ('slices' in metadata and metadata['slices'] > 1) or (
                        'frames' in metadata and metadata['frames'] > 1):
                    images = tif.pages[0].asarray()
                else:
                    images = [tif.pages[0].asarray()]
            elif len(tif.pages) > 1:
                images = list()
                for i, page in enumerate(tif.pages):
                    images.append(page.asarray())

            ax_dct = {n: k for k, n in enumerate(tif.series[0].axes)}
            ax_dct = dict(sorted(ax_dct.items(), key=lambda item: item[1]))  # dict sorted by value
            shape = tif.series[0].shape
            frames = metadata['frames'] if 'frames' in metadata else 1
            ts = np.linspace(start=0, stop=frames * dt, num=frames) if dt is not None else None
            return MetadataImageSeries(reader="tifffile",
                                       images=np.asarray(images), pix_per_um=res, um_per_pix=1. / res,
                                       um_per_z=1,  # TODO: pass to um
                                       time_interval=dt, frames=frames, timestamps=ts,
                                       channels=metadata['channels'] if 'channels' in metadata else 1,
                                       zstacks=shape[ax_dct['Z']] if 'Z' in ax_dct else 1,
                                       width=width, height=height, series=tif.series[0],
                                       intensity_ranges=metadata['Ranges'] if 'Ranges' in metadata else None,
                                       axes=ax_dct)


def retrieve_image(md_img: MetadataImageSeries, frame=0, channel=0, z=0):
    nimgs = len(md_img.images)
    n_channels = int(nimgs / md_img.frames)
    ix = frame * n_channels + channel
    image_arr = md_img.images
    logger.debug("Retrieving frame %d of channel %d (index=%d)" % (frame, channel, ix))
    return MetadataImage(
        reader="tiff_loader",
        image=image_arr[ix], pix_per_um=md_img.pix_per_um, um_per_pix=md_img.um_per_pix,
        time_interval=None, timestamp=None, frame=frame,
        channel=channel,
        z=z, width=md_img.width, height=md_img.height,
        intensity_range=[image_arr[ix].min(), image_arr[ix].max()]
    )
