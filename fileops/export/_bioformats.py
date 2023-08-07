import os.path
from typing import List

import numpy as np
from tifffile import imwrite

from fileops.cached import CachedImageFile
from fileops.cached.cached_image_file import ensure_dir
from fileops.image import OMEImageFile
from fileops.image.exceptions import FrameNotFoundError
from fileops.logger import get_logger

log = get_logger(name='export')


def bioformats_to_tiffseries(path, img_struct: CachedImageFile, save_folder='_vol_paraview'):
    log.info("Exporting bioformats file to series of tiff file volumes.")
    base_dir = os.path.dirname(path)
    sav_path = os.path.join(base_dir, save_folder)
    ensure_dir(os.path.join(sav_path, 'dummy'))

    image = np.empty(shape=(len(img_struct.zstacks), *img_struct.image(0).image.shape), dtype=np.uint16)
    for j, c in enumerate(img_struct.channels):
        for fr in img_struct.frames:
            for i, z in enumerate(img_struct.zstacks):
                ix = img_struct.ix_at(c=j, z=z, t=fr)
                mdimg = img_struct.image(ix)
                image[i, :, :] = mdimg.image
            fname = f'C{c:02d}T{fr:04d}_vol.tiff'
            fpath = os.path.join(sav_path, fname)
            log.debug(f"Saving image {fname} in cache (path={fpath}).")
            imwrite(fpath, np.array(image), imagej=True, metadata={'order': 'ZXY'})


def bioformats_to_ndarray_zstack(img_struct: OMEImageFile, roi=None, channel=0, frame=0):
    log.info("Exporting bioformats file to a single ndarray representing a z-stack volume.")

    if roi is not None:
        log.debug("Processing ROI definition that is in configuration file")
        w = abs(roi.right - roi.left)
        h = abs(roi.top - roi.bottom)
        x0 = int(roi.left)
        y0 = int(roi.top)
        x1 = int(x0 + w)
        y1 = int(y0 + h)
    else:
        log.debug("No ROI definition in configuration file")
        w = img_struct.width
        h = img_struct.height
        x0 = 0
        y0 = 0
        x1 = w
        y1 = h

    image = np.empty(shape=(len(img_struct.zstacks), h, w), dtype=np.uint16)
    for i, z in enumerate(img_struct.zstacks):
        log.debug(f"c={channel}, z={z}, t={frame}")
        ix = img_struct.ix_at(c=channel, z=z, t=frame)
        mdimg = img_struct.image(ix)
        image[i, :, :] = mdimg.image[y0:y1, x0:x1]

    # convert to 8 bit data
    image = ((image - image.min()) / (image.ptp() / 255.0)).astype(np.uint8)

    return image


def bioformats_to_ndarray_zstack_timeseries(img_struct: OMEImageFile, frames: List[int], roi=None, channel=0):
    """
    Constructs a memory-intensive numpy ndarray of a whole OMEImageFile timeseries.
    Warning, it can lead to memory issues on machines with low RAM.
    """
    log.info("Exporting bioformats file to and ndarray representing a series of z-stack volumes.")

    if roi is not None:
        log.debug("Processing ROI definition that is in configuration file")
        w = abs(roi.right - roi.left)
        h = abs(roi.top - roi.bottom)
        x0 = int(roi.left)
        y0 = int(roi.top)
        x1 = int(x0 + w)
        y1 = int(y0 + h)
    else:
        log.debug("No ROI definition in configuration file")
        w = img_struct.width
        h = img_struct.height
        x0 = 0
        y0 = 0
        x1 = w
        y1 = h

    image = np.empty(shape=(len(frames), len(img_struct.zstacks), h, w), dtype=np.uint16)
    try:
        for i, frame in enumerate(frames):
            img_z = np.empty(shape=(len(img_struct.zstacks), h, w), dtype=np.uint16)
            for j, z in enumerate(img_struct.zstacks):
                log.debug(f"c={channel}, z={z}, t={frame}")
                ix = img_struct.ix_at(c=channel, z=z, t=frame)
                mdimg = img_struct.image(ix)
                img_z[j, :, :] = mdimg.image[y0:y1, x0:x1]

            # assign volume into timeseries numpy array
            image[i, :, :, :] = img_z
    except (FrameNotFoundError, IndexError):
        print("FrameNotFoundError or IndexError")
    # convert to 8 bit data and normalize intensities across whole timeseries
    # image = exposure.equalize_hist(image)
    # image = exposure.rescale_intensity(image)
    image = ((image - image.min()) / (image.ptp() / 255.0)).astype(np.uint8)
    print(image.dtype)
    return image
