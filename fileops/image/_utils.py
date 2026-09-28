import os
from pathlib import Path
from typing import List

import tifffile as tf


def find_associated_files(path, prefix) -> List[Path]:
    """Find files in *path* whose names start with *prefix*."""
    out = list()
    for root, directories, filenames in os.walk(path):
        for file in filenames:
            if len(file) > len(prefix) and file[:len(prefix)] == prefix:
                out.append(file)
    return out


def resolve_pix_per_um_from_tiff_tags(keyframe_or_page, resunit_cls=None) -> float:
    """Extract pixels-per-um from XResolution/ResolutionUnit TIFF tags.

    Parameters
    ----------
    keyframe_or_page : tifffile page or keyframe
        A TIFF page with ``tags`` attribute (e.g. ``tif.pages.keyframe`` or
        ``tif.pages[0]``).
    resunit_cls : type, optional
        The tifffile RESUNIT enum to compare against.  Defaults to
        ``tf.TIFF.RESUNIT.CENTIMETER``.

    Returns
    -------
    float
        Pixels per micrometre (defaults to 1 if tags are absent).
    """
    if resunit_cls is None:
        resunit_cls = tf.RESUNIT.CENTIMETER

    if 'XResolution' not in keyframe_or_page.tags:
        return 1.0

    xr = keyframe_or_page.tags['XResolution'].value
    try:
        num, den = float(xr[0]), float(xr[1])
    except (IndexError, TypeError, ValueError):
        return 1.0

    # MicroManager writes XResolution = (4294967295, 1) — i.e. 2**32 - 1, all bits
    # set — as a sentinel meaning "no pixel-size calibration" (with ResolutionUnit=3,
    # cm). Read literally, it yields ~429496.73 px/um, an absurd calibration that
    # cascades into broken physical scaling downstream (min_size computations,
    # pixel<->micron conversions, ...).
    if num <= 0 or den <= 0 or int(num) == 4294967295:
        return 1.0

    res = num / den  # pixels per resolution unit (raw, before unit conversion)
    if keyframe_or_page.tags['ResolutionUnit'].value == resunit_cls:
        res = res / 1e4
    if res >= 1e6:  # implausible calibration; treat like an absent tag
        return 1.0
    return res
