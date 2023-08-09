import configparser
import os
from collections import namedtuple
from pathlib import Path
from typing import List

from roifile import ImagejRoi

from fileops.image import MicroManagerSingleImageStack
from fileops.logger import get_logger

log = get_logger(name='export')
# ------------------------------------------------------------------------------------------------------------------
#  routines for handling of configuration files
# ------------------------------------------------------------------------------------------------------------------
ExportConfig = namedtuple('ExportConfig',
                          ['series', 'frames', 'channels', 'path', 'name', 'image_file', 'roi', 'um_per_z', ])


def _load_project_file(path) -> configparser.ConfigParser:
    prj = configparser.ConfigParser()
    prj.read(path)

    return prj


def read_config(cfg_path, frame_from_roi=True) -> ExportConfig:
    cfg = _load_project_file(cfg_path)

    im_series = int(cfg["DATA"]["series"])
    im_channel = cfg["DATA"]["channel"]
    img_path = Path(cfg["DATA"]["image"])
    im_frame = None

    # img_file = OMEImageFile(img_path.as_posix(), image_series=im_series)
    img_file = MicroManagerSingleImageStack(img_path.as_posix())

    # check if frame data is in the configuration file
    if "frame" in cfg["DATA"]:
        im_frame = cfg["DATA"]["frame"]
        im_frame = range(img_file.n_frames) if im_frame == "all" else [int(im_frame)]

    # process ROI path
    roi = None
    if "ROI" in cfg["DATA"]:
        roi_path = Path(cfg["DATA"]["ROI"])
        if not roi_path.is_absolute():
            roi_path = cfg_path.parent / roi_path
            roi = ImagejRoi.fromfile(roi_path)

            # update frame data from ROI file if applicable
            if frame_from_roi and roi:
                im_frame = [roi.t_position]

    return ExportConfig(series=im_series,
                        frames=im_frame,
                        channels=range(img_file.n_channels) if im_channel == "all" else [int(im_channel)],
                        path=cfg_path.parent,
                        name=cfg_path.name,
                        image_file=img_file,
                        um_per_z=float(cfg["DATA"]["um_per_z"]) if "um_per_z" in cfg["DATA"] else img_file.um_per_z,
                        roi=roi)


def search_config_files(ini_path: Path) -> List[Path]:
    out = []
    for root, directories, filenames in os.walk(ini_path):
        for file in filenames:
            path= Path(root)/file
            if os.path.isfile(path) and path.suffix == '.cfg':
                out.append(path)
    return out
