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
                          ['series', 'frames', 'channels', 'failover_dt', 'failover_mag',
                           'path', 'name', 'image_file', 'roi', 'um_per_z',
                           'title', 'fps', 'movie_filename'])


def read_config(cfg_path) -> ExportConfig:
    cfg = configparser.ConfigParser()
    cfg.read(cfg_path)

    assert "DATA" in cfg, "No header with the name DATA."

    im_series = int(cfg["DATA"]["series"]) if "series" in cfg["DATA"] else -1
    im_channel = cfg["DATA"]["channel"]
    img_path = Path(cfg["DATA"]["image"])
    im_frame = None

    kwargs = {
        'failover_dt':  cfg["DATA"]["override_dt"] if "override_dt" in cfg["DATA"] else None,
        "failover_mag": cfg["DATA"]["override_mag"] if "override_mag" in cfg["DATA"] else None,
    }
    # img_file = OMEImageFile(img_path.as_posix(), image_series=im_series)
    img_file = MicroManagerSingleImageStack(img_path, **kwargs)

    # check if frame data is in the configuration file
    if "frame" in cfg["DATA"]:
        _frame = cfg["DATA"]["frame"]
        im_frame = range(img_file.n_frames) if _frame == "all" else [int(_frame)]

    # process ROI path
    roi = None
    if "ROI" in cfg["DATA"]:
        roi_path = Path(cfg["DATA"]["ROI"])
        if not roi_path.is_absolute():
            roi_path = cfg_path.parent / roi_path
            roi = ImagejRoi.fromfile(roi_path)

    if im_frame is None:
        im_frame = range(img_file.n_frames)

    if "MOVIE" in cfg:
        title = cfg["MOVIE"]["title"]
        fps = cfg["MOVIE"]["fps"]
        movie_filename = cfg["MOVIE"]["filename"]
    else:
        title = fps = movie_filename = ''

    return ExportConfig(series=im_series,
                        frames=im_frame,
                        channels=range(img_file.n_channels) if im_channel == "all" else eval(im_channel),
                        failover_dt=cfg["DATA"]["override_dt"] if "override_dt" in cfg["DATA"] else None,
                        failover_mag=cfg["DATA"]["override_mag"] if "override_mag" in cfg["DATA"] else None,
                        path=cfg_path.parent,
                        name=cfg_path.name,
                        image_file=img_file,
                        um_per_z=float(cfg["DATA"]["um_per_z"]) if "um_per_z" in cfg["DATA"] else img_file.um_per_z,
                        roi=roi,
                        title=title,
                        fps=int(fps) if fps else 1,
                        movie_filename=movie_filename)


def search_config_files(ini_path: Path) -> List[Path]:
    out = []
    for root, directories, filenames in os.walk(ini_path):
        for file in filenames:
            path = Path(root) / file
            if os.path.isfile(path) and path.suffix == '.cfg':
                out.append(path)
    return sorted(out)
