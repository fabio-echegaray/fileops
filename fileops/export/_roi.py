import re
import traceback
from collections import namedtuple
from pathlib import Path
from typing import NamedTuple, List

import numpy as np
import pandas as pd
from roifile import ImagejRoi, ROI_TYPE

from fileops import get_logger
from ._trackmanager_icy import parse_track_xml as trackmanager_icy_xml
from ._trackmate import parse_track_xml as trackmate_xml

log = get_logger(name='roi_tools')

rect_params = namedtuple("rect_param", ["X", "Y", "W", "H"])

# length unit -> micrometres (for metric ROI geometry)
_LENGTH_TO_UM = {
    'um': 1.0,
    'µm': 1.0,
    'μm': 1.0,
    'nm': 1e-3,
    'mm': 1e3,
    'm': 1e6,
}

# number with optional length unit, e.g. "10.3um", "20", "0.1 mm", "1.07e-4 m"
_NUMBER_RE = re.compile(
    r"^\s*([+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)\s*([a-zA-Zµμm]+)?\s*$")


class ConfigROI(NamedTuple):
    header: str
    configfile: Path
    geometry: ImagejRoi | List[ImagejRoi]


def rectangle_roi(rect_p: rect_params, center_is_middle=True) -> ImagejRoi:
    x0 = int(rect_p.X - rect_p.W / 2) if center_is_middle else rect_p.X
    y0 = int(rect_p.Y - rect_p.H / 2) if center_is_middle else rect_p.Y
    x1 = int(rect_p.X + rect_p.W / 2) if center_is_middle else rect_p.X + rect_p.W
    y1 = int(rect_p.Y + rect_p.H / 2) if center_is_middle else rect_p.Y + rect_p.H
    rect_roi = ImagejRoi.frompoints(np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1]]))
    rect_roi.roitype = ROI_TYPE.RECT

    return rect_roi


def parse_geometry_value(spec: str, pix_per_um: float | None = None) -> float:
    """Parse one ROI geometry argument into pixels.

    A bare number is already in pixels. A number carrying a length unit
    (``um``/``µm``/``μm``/``nm``/``mm``/``m``) is converted to pixels using
    ``pix_per_um``; a metric value therefore requires the image calibration.
    """
    m = _NUMBER_RE.match(spec)
    if m is None:
        raise ValueError(f"Unsupported ROI geometry value: {spec!r}.")
    value, unit = float(m.group(1)), m.group(2)
    if unit is None:
        return value
    if unit not in _LENGTH_TO_UM:
        raise ValueError(f"Unsupported ROI geometry unit: {unit!r} in {spec!r}.")
    if pix_per_um is None or pix_per_um <= 0:
        raise ValueError(
            f"ROI geometry {spec!r} uses metric units but no pixel-size "
            f"calibration is available; provide a pix_per_um scale.")
    return value * _LENGTH_TO_UM[unit] * pix_per_um


def parse_geometry_args(geom: str, pix_per_um: float | None = None):
    """Split a geometry string into its shape name and parsed numeric arguments.

    Returns ``(name, [pixel_values])``. Supports per-value metric units, e.g.
    ``Rectangle(10.3um, 20.1um, 40.45um, 60.324um)``.
    """
    if "(" not in geom or not geom.endswith(")"):
        raise ValueError(f"Unsupported ROI geometry: {geom!r}.")
    name, _, args = geom.partition("(")
    nums = [parse_geometry_value(p, pix_per_um) for p in args[:-1].split(",")]
    return name, nums


def parse_static_geometry(geom: str, pix_per_um: float | None = None) -> ImagejRoi:
    """Parse a static ROI definition string into an ImagejRoi.

    Supported forms (all centered on ``(x, y)``):
      ``Square(x, y, side)``
      ``Rectangle(x, y, width, height)``

    Arguments are pixels by default, or metric when given a length unit, e.g.
    ``Rectangle(10.3um, 20.1um, 40.45um, 60.324um)`` (needs ``pix_per_um``).
    """
    name, nums = parse_geometry_args(geom, pix_per_um)
    if name == "Square":
        if len(nums) != 3:
            raise ValueError(f"Square geometry needs 3 numbers: {geom!r}.")
        x, y, a = nums
        return rectangle_roi(rect_params(X=x, Y=y, W=a, H=a))
    if name == "Rectangle":
        if len(nums) != 4:
            raise ValueError(f"Rectangle geometry needs 4 numbers: {geom!r}.")
        x, y, w, h = nums
        return rectangle_roi(rect_params(X=x, Y=y, W=w, H=h))
    raise ValueError(f"Unsupported ROI geometry: {geom!r}.")


def rectangle_roi_following(trajectory: Path | pd.DataFrame, rect_p=rect_params(X=0, Y=0, W=1, H=1)) -> List[ImagejRoi]:
    if isinstance(trajectory, Path):
        if trajectory.suffix.lower() == ".xml":
            parsers = [
                ("Trackmate", trackmate_xml),
                ("TrackManager (Icy)", trackmanager_icy_xml),
            ]
            log.debug(f"Attempting to open track file {trajectory}")
            for name, parser in parsers:
                try:
                    trk = parser(trajectory)
                    log.debug(f"Parsed as {name}")
                    break
                except Exception as e:
                    log.error(e)
                    log.error(traceback.print_exc())
                    last_exc = e
                    # continue trying
            else:
                raise RuntimeError(f"Unable to parse file with known formats {last_exc}")
    elif isinstance(trajectory, pd.DataFrame):
        if not ["X", "Y", "Track", "Frame"] in trajectory:
            raise ValueError("Trajectory dataframe does not contain needed columns.")
        else:
            trk = trajectory
            trk.rename(columns={'X': 'x', 'Y': 'y', 'Track': 'track_id', 'Frame': 't'}, inplace=True)
    else:
        raise ValueError("Incorrect trajectory definition.")

    # create ROI
    rois = list()
    for ix, r in trk.sort_values(by="t").iterrows():
        roi = rectangle_roi(rect_params(X=r["x"], Y=r["y"], W=rect_p.W, H=rect_p.H))
        roi.t_position = r["t"]
        roi.z_position = r["z"]
        rois.append(roi)

    return rois
