import configparser
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Union
from typing import NamedTuple

import pandas as pd
from pytrackmate import trackmate_peak_import
from roifile import ImagejRoi

import fileops
from fileops.export.config_data_section import read_data_section
from fileops.image import ImageFile
from fileops.logger import get_logger
from fileops.pathutils import ensure_dir
from fileops.plugins import HeaderReaderPlugin

log = get_logger(name='export')


# ----------------------------------------------------------------------------------------------------------------------
#  routines for handling of configuration files
# ------------------------------------------------------------------------------------------------------------------
class ConfigVolume(NamedTuple):
    header: str
    configfile: Path
    series: int
    frames: List[int]
    channels: List[int]
    image_file: Union[ImageFile, None]
    roi: ImagejRoi
    um_per_z: float
    filename: str


class ConfigTrack(NamedTuple):
    header: str
    title: str
    configfile: Path
    track_df: pd.DataFrame
    store_path: Path


@dataclass
class ExportConfig:
    config_file: configparser.ConfigParser
    path: Union[Path, None]
    name: Union[str, None]
    tracks: List[ConfigTrack]


def read_config(cfg_path: Path) -> ExportConfig:
    cfg_path = cfg_path.absolute()
    if not cfg_path.exists():
        raise FileNotFoundError(f"Configuration file {cfg_path} does not exist!")
    cfg = configparser.ConfigParser()
    cfg.read(cfg_path)

    if "DATA" not in cfg:
        raise SyntaxError(f"No header DATA in file {cfg_path}.")

    cfg_tracks = read_config_tracks(cfg_path)

    exp_config = ExportConfig(
        config_file=cfg,
        path=cfg_path.parent,
        name=cfg_path.name,
        tracks=cfg_tracks
    )

    for p in fileops.config_type_plugins:
        t_name = p.name
        header_reader_name = f"{t_name}_header_reader"
        for h in fileops.header_reader_plugins:
            if h.name == header_reader_name:
                clz = h.load()
                if not issubclass(clz, HeaderReaderPlugin):
                    continue
                cinst = clz(cfg_path)
                if cinst.has_valid_header():
                    setattr(exp_config, t_name + "s", cinst.process())

    return exp_config


def read_config_tracks(cfg_path) -> List[ConfigTrack]:
    cfg, img_file, param_override, roi = read_data_section(cfg_path)

    panel_tracks = [s for s in cfg.sections() if s.startswith("TRACKMATE")]
    if len(panel_tracks) == 0:
        log.warning(f"No headers with name TRACKMATE in file {cfg_path}.")
        return []

    # process TRACK sections
    panel_def = list()
    for pan in panel_tracks:
        trk_path = Path(cfg[pan]["path"])
        if not trk_path.is_absolute():
            trk_path = cfg_path.parent / trk_path

        trk = trackmate_peak_import(trk_path, get_tracks=True)
        trk.rename(columns={'x': 'x_um', 'y': 'y_um'}, inplace=True)
        trk["frame"] = trk["t"].astype(int)
        trk["track_id"] = trk["label"]
        trk["track_name"] = trk["label"].apply(lambda lbl: f"track_{int(lbl):04d}")
        panel_def.append(ConfigTrack(
            header=pan,
            configfile=cfg_path,
            store_path=cfg_path,
            title=f"trackmate file {trk_path}",
            track_df=trk
        ))
    return panel_def


_rowcol_dict = {
    "channel":  "channel",
    "channels": "channel",
    "frame":    "frame",
    "frames":   "frame"
}


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
    if not cfg_path.exists():
        raise FileNotFoundError
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
            "bitrate":      cfg["MOVIE"]["bitrate"] if "bitrate" in cfg["MOVIE"] else "500k",
            "t_collection": col_m,
            "t_incubation": inc_m,
            "fps":          cfg["MOVIE"]["fps"] if "fps" in cfg["MOVIE"] else 10,
            "layout":       cfg["MOVIE"]["layout"] if "layout" in cfg["MOVIE"] else "twoch",
            "z_projection": cfg["MOVIE"]["z_projection"] if "z_projection" in cfg["MOVIE"] else "all-max",
        })

    df = pd.DataFrame(dfl)
    return df
