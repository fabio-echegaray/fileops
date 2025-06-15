import os.path
from pathlib import Path
from typing import List, Dict, Tuple

import numpy as np
from matplotlib import pyplot as plt
from tifffile import imwrite, imread

from fileops.image._bleach_correction import photobleach_correct, bleach_func
from fileops.pathutils import ensure_dir
from fileops.export.config import ExportConfig
from fileops.image import OMEImageFile
from fileops.image.exceptions import FrameNotFoundError
from fileops.logger import get_logger

log = get_logger(name='export')


def bioformats_to_tiffseries(cfg_struct: ExportConfig, save_path=Path('_vol_paraview'), until_frame=np.inf) -> Tuple[
    np.array, Dict]:
    log.info("Exporting bioformats file to series of tiff file volumes.")
    save_path = ensure_dir(save_path)

    dct = dict()
    img_struct = cfg_struct.image_file
    image = np.empty(shape=(len(img_struct.zstacks), img_struct.width, img_struct.height), dtype=np.uint16)
    for j, c in enumerate(cfg_struct.channels):
        print(f"{j=} {c=}")
        dct[f"ch{c:01d}"] = {
            "files":  [],
            "minmax": [],
            "sum":    [],
            "mean":   [],
            "std":    [],
        }
        ensure_dir(save_path / f"ch{c:01d}")
        for fr in cfg_struct.frames:
            if fr > until_frame:
                break

            fname = f'C{c:02d}T{fr:04d}_vol.tiff'
            fpath = (save_path / f"ch{c:01d}" / fname).absolute()

            dct[f"ch{c:01d}"]["files"].append(fpath.as_posix())

            log.debug(f"Attempting to save image {fname} in path={fpath}.")
            if not os.path.exists(fpath):
                for i, z in enumerate(img_struct.zstacks):
                    try:
                        ix = img_struct.ix_at(c=j, z=z, t=fr)
                        mdimg = img_struct.image(ix)
                        if mdimg and hasattr(mdimg, "image") and mdimg.image is not None:
                            image[i, :, :] = mdimg.image
                    except FrameNotFoundError or IndexError as e:
                        print(f"Frame index corresponding to  c={j} z={z} t={fr} not found (file corrupted?)")
                imwrite(fpath, np.array(image), imagej=True, metadata={'order': 'ZXY'})
            else:
                print(f"skipping file {fpath.as_posix()}")
                image = imread(fpath)
            # add stats
            dct[f"ch{c:01d}"]["minmax"].append((np.min(image), np.max(image)))
            dct[f"ch{c:01d}"]["std"].append(np.std(image))
            dct[f"ch{c:01d}"]["mean"].append(np.mean(image))
            dct[f"ch{c:01d}"]["sum"].append(np.mean(image))

        agg_intensities = np.array(dct[f"ch{c:01d}"]["mean"])
        xdata = np.array(range(len(agg_intensities)))
        pbparms = photobleach_correct(agg_intensities)

        dct[f"ch{c:01d}"]["photobleach_params"] = pbparms

        # --------------------------------------------------------------------------------------------------------------
        #  Plot the curve fit with de-trended data
        # --------------------------------------------------------------------------------------------------------------
        f = plt.figure()
        ax = f.gca()
        ax.scatter(xdata, agg_intensities, c='b', label='Mean Intensity')

        dtrend = int(dct[f"ch{c:01d}"]['mean'][0] - pbparms[2]) - int(pbparms[0]) * np.exp(
            -np.round(pbparms[1], 4) * xdata)
        ax.scatter(xdata, agg_intensities + dtrend, c='k', label='Corrected Intensity')

        ax.plot(xdata, bleach_func(xdata, *pbparms), 'r-',
                label='fit: a=%5.3f, b=%5.3f, c=%5.3f' % tuple(pbparms))
        ax.plot(xdata, dtrend, 'y-', label='Values Added')
        ax.text(0.7, .1, r"$f(x)=a \cdot e^{-b \cdot x} +c$", color="k", fontsize=10, transform=ax.transAxes)

        ax.set_xlabel('Frame')
        ax.set_ylabel('Avg. Intensity [au]')
        ax.legend()
        f.savefig(save_path / f'ch{c:01d}_photobleach.pdf')

    return image, dct


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
