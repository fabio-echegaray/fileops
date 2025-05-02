import configparser
import os
import re
from pathlib import Path
from typing import List, Dict, Union, Iterable
from typing import NamedTuple

import pandas as pd
from roifile import ImagejRoi

from fileops.image import ImageFile
from fileops.image.factory import load_image_file
from fileops.logger import get_logger
from fileops.pathutils import ensure_dir

log = get_logger(name='export')


# ------------------------------------------------------------------------------------------------------------------
#  routines for handling of configuration files
# ------------------------------------------------------------------------------------------------------------------
class ExportConfig(NamedTuple):
    series: int
    frames: Iterable[int]
    channels: List[int]
    failover_dt: Union[float, None]
    failover_mag: Union[float, None]
    path: Path
    name: str
    image_file: Union[ImageFile, None]
    roi: ImagejRoi
    um_per_z: float
    title: str
    fps: int
    movie_filename: str
    layout: str


def read_config(cfg_path) -> ExportConfig:
    cfg = configparser.ConfigParser()
    cfg.read(cfg_path)

    assert "DATA" in cfg, f"No header DATA in file {cfg_path}."

    im_series = int(cfg["DATA"]["series"]) if "series" in cfg["DATA"] else -1
    im_channel = cfg["DATA"]["channel"]
    img_path = Path(cfg["DATA"]["image"])
    im_frame = None

    kwargs = {
        "failover_dt":  cfg["DATA"]["override_dt"] if "override_dt" in cfg["DATA"] else None,
        "failover_mag": cfg["DATA"]["override_mag"] if "override_mag" in cfg["DATA"] else None,
    }

    if not img_path.is_absolute():
        img_path = cfg_path.parent / img_path

    if "use_loader_class" in cfg["DATA"]:
        _cls = eval(f"{cfg['DATA']['use_loader_class']}")
        img_file = _cls(img_path, **kwargs)
    else:
        img_file = load_image_file(img_path, **kwargs)
    assert img_file, "Image file not found."

    # check if frame data is in the configuration file
    if "frame" in cfg["DATA"]:
        try:
            _frame = cfg["DATA"]["frame"]
            im_frame = range(img_file.n_frames) if _frame == "all" else [int(_frame)]
        except ValueError as e:
            im_frame = range(img_file.n_frames)

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
                        movie_filename=movie_filename,
                        layout=cfg["MOVIE"]["layout"] if "MOVIE" in cfg and "layout" in cfg["MOVIE"] else "twoch-comp")


def create_cfg_file(path: Path, contents: Dict):
    ensure_dir(path.parent)

    config = configparser.ConfigParser()
    config.update(contents)
    with open(path, "w") as configfile:
        config.write(configfile)


def search_config_files(ini_path: Path) -> List[Path]:
    out = []
    for root, directories, filenames in os.walk(ini_path):
        for file in filenames:
            path = Path(root) / file
            if os.path.isfile(path) and path.suffix == ".cfg":
                out.append(path)
    return sorted(out)


def _read_cfg_file(cfg_path) -> configparser.ConfigParser:
    cfg = configparser.ConfigParser()
    cfg.read(cfg_path)
    return cfg


def build_config_list(ini_path: Path) -> pd.DataFrame:
    cfg_files = search_config_files(ini_path)
    dfl = list()
    for f in cfg_files:
        cfg = _read_cfg_file(f)

        # the following code extracts time of collection and incubation.
        # However, it is not complete and lacks some use cases.
        col_m = inc_m = None

        col = re.search(r'([0-9]+)hr collection', cfg["MOVIE"]["description"])
        inc = re.search(r'([0-9:]+)(hr)? incubation', cfg["MOVIE"]["description"])

        col_m = int(col.groups()[0]) * 60 if col else None
        if inc:
            if ":" in inc.groups()[0]:
                hr, min = inc.groups()[0].split(":")
                inc_m = int(hr) * 60 + int(min)
            else:
                inc_m = int(inc.groups()[0]) * 60

        # now append the data collected
        dfl.append({
            "cfg_path":     f.as_posix(),
            "cfg_folder":   f.parent.name,
            "movie_name":   cfg["MOVIE"]["filename"] if "filename" in _read_cfg_file(f)["MOVIE"] else "",
            "image":        cfg["DATA"]["image"],
            "session_fld":  Path(cfg["DATA"]["image"]).parent.parent.name,
            "img_fld":      Path(cfg["DATA"]["image"]).parent.name,
            "title":        cfg["MOVIE"]["title"],
            "description":  cfg["MOVIE"]["description"],
            "t_collection": col_m,
            "t_incubation": inc_m,
            "fps":          cfg["MOVIE"]["fps"] if "fps" in cfg["MOVIE"] else 10,
            "layout":       cfg["MOVIE"]["layout"] if "layout" in cfg["MOVIE"] else "twoch",
            "z_projection": cfg["MOVIE"]["z_projection"] if "z_projection" in cfg["MOVIE"] else "all-max",
        })

    df = pd.DataFrame(dfl)
    return df
