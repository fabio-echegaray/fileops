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


class ConfigROI(NamedTuple):
    header: str
    configfile: Path
    geometry: ImagejRoi | List[ImagejRoi]
    plot: bool


def rectangle_roi(rect_p: rect_params, center_is_middle=True) -> ImagejRoi:
    x0 = int(rect_p.X - rect_p.W / 2) if center_is_middle else rect_p.X
    y0 = int(rect_p.Y - rect_p.H / 2) if center_is_middle else rect_p.Y
    x1 = int(rect_p.X + rect_p.W / 2) if center_is_middle else rect_p.X + rect_p.W
    y1 = int(rect_p.Y + rect_p.H / 2) if center_is_middle else rect_p.Y + rect_p.H
    rect_roi = ImagejRoi.frompoints(np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1]]))
    rect_roi.roitype = ROI_TYPE.RECT

    return rect_roi


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
                    last_exc = e
                    # continue trying
            else:
                raise RuntimeError("Unable to parse file with known formats")
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
