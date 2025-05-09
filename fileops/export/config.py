import ast
import configparser
import os
import re
from pathlib import Path
from typing import List, Dict, Union, Iterable
from typing import NamedTuple

import pandas as pd
from roifile import ImagejRoi

from fileops.export._param_override import ParameterOverride
from fileops.image import ImageFile
from fileops.image.factory import load_image_file
from fileops.logger import get_logger
from fileops.pathutils import ensure_dir

log = get_logger(name='export')


# ------------------------------------------------------------------------------------------------------------------
#  routines for handling of configuration files
# ------------------------------------------------------------------------------------------------------------------
class ConfigMovie(NamedTuple):
    header: str
    series: int
    frames: Iterable[int]
    channels: List[int]
    zstack_fn: str
    scalebar: float
    override_dt: Union[float, None]
    image_file: Union[ImageFile, None]
    roi: ImagejRoi
    um_per_z: float
    title: str
    fps: int
    bitrate: str  # bitrate in a format that ffmpeg understands
    movie_filename: str
    layout: str


class ConfigPanel(NamedTuple):
    header: str
    series: int
    frames: List[int]
    channels: List[int]
    zstacks: List[int]
    scalebar: float
    override_dt: Union[float, None]
    image_file: Union[ImageFile, None]
    channel_render_parameters: Dict
    roi: ImagejRoi
    columns: str
    rows: str
    type: str
    um_per_z: float
    title: str
    filename: str
    layout: str


class ConfigVolume(NamedTuple):
    header: str
    series: int
    frames: List[int]
    channels: List[int]
    image_file: Union[ImageFile, None]
    roi: ImagejRoi
    um_per_z: float
    filename: str


class ExportConfig(NamedTuple):
    config_file: configparser.ConfigParser
    path: Union[Path, None]
    name: Union[str, None]
    movies: List[ConfigMovie]
    panels: List[ConfigPanel]


def _process_overrides(section, param_override, img_file: ImageFile):
    # override frames if defined again in section
    # check if frame data is in the configuration file
    _fr_lbl = [l for l in section.keys() if l[:5] == "frame"]
    if len(_fr_lbl) == 1:
        _fr_lbl = _fr_lbl[0]
        try:
            _frame = section[_fr_lbl]
            if _frame == "all":
                param_override.frames = range(img_file.n_frames)
            elif ".." in _frame:
                _f = _frame.split("..")
                param_override.frames = range(int(_f[0]), int(_f[1]))
            else:
                param_override.frames = [int(_frame)]
        except ValueError as e:
            log.error(f"error parsing frames in section {section}")
            pass

    # check if channel data is in the configuration file
    _ch_lbl = "channel" if "channel" in section else "channels" if "channels" in section else None
    if _ch_lbl is not None:
        try:
            _channel = section[_ch_lbl]
            param_override.channels = range(img_file.n_channels) if _channel == "all" else [int(_channel)]
        except ValueError as e:
            pass

    # check if zstack data is in the configuration file
    _z_lbl = "zstack" if "zstack" in section else "zstacks" if "zstacks" in section else None
    if "zstack" in section:
        try:
            _z = section[_z_lbl]
            param_override.zstacks = range(img_file.n_zstacks) if _z == "all" else [int(_z)]
        except ValueError as e:
            pass

    return param_override


def _read_data_section(cfg_path):
    cfg = configparser.ConfigParser()
    cfg.read(cfg_path)

    assert "DATA" in cfg, f"No header DATA in file {cfg_path}."

    img_path = Path(cfg["DATA"]["image"])
    if not img_path.is_absolute():
        img_path = cfg_path.parent / img_path
    kwargs = {
        "override_dt": cfg["DATA"]["override_dt"] if "override_dt" in cfg["DATA"] else None,
    }
    if "use_loader_class" in cfg["DATA"]:
        _cls = eval(f"{cfg['DATA']['use_loader_class']}")
        img_file: ImageFile = _cls(img_path, **kwargs)
    else:
        img_file = load_image_file(img_path, **kwargs)
    assert img_file, "Image file not found."

    param_override = _process_overrides(cfg["DATA"], ParameterOverride(img_file), img_file)

    # process ROI path
    roi = None
    if "ROI" in cfg["DATA"]:
        roi_path = Path(cfg["DATA"]["ROI"])
        if not roi_path.is_absolute():
            roi_path = cfg_path.parent / roi_path
            roi = ImagejRoi.fromfile(roi_path)

    return cfg, img_file, param_override, roi


def read_config(cfg_path) -> ExportConfig:
    cfg = configparser.ConfigParser()
    cfg.read(cfg_path)

    if "DATA" not in cfg:
        log.error(f"No header DATA in file {cfg_path}.")
        return ExportConfig(
            config_file=cfg,
            path=None,
            name=None,
            movies=[],
            panels=[]
        )

    cfg_movie = read_config_movie(cfg_path)
    cfg_panel = read_config_panel(cfg_path)

    return ExportConfig(
        config_file=cfg,
        path=cfg_path.parent,
        name=cfg_path.name,
        movies=cfg_movie,
        panels=cfg_panel
    )


def read_config_movie(cfg_path) -> List[ConfigMovie]:
    cfg, img_file, param_override, roi = _read_data_section(cfg_path)

    movie_headers = [s for s in cfg.sections() if s[:5].upper() == "MOVIE"]
    if len(movie_headers) == 0:
        log.warning(f"No headers with name MOVIE in file {cfg_path}.")
        return []

    # process MOVIE sections
    movie_def = list()
    for mov in movie_headers:
        title = cfg[mov]["title"]
        fps = cfg[mov]["fps"]
        movie_filename = cfg[mov]["filename"]
        param_override = _process_overrides(cfg[mov], param_override, img_file)

        movie_def.append(ConfigMovie(
            header=mov,
            series=img_file.series,
            frames=param_override.frames,
            channels=param_override.channels,
            scalebar=float(cfg[mov]["scalebar"]) if "scalebar" in cfg[mov] else None,
            override_dt=param_override.dt,
            image_file=img_file,
            zstack_fn=cfg[mov]["zstack_fn"] if "zstack_fn" in cfg[mov] else "all-max",
            um_per_z=float(cfg["DATA"]["um_per_z"]) if "um_per_z" in cfg["DATA"] else img_file.um_per_z,
            roi=roi,
            title=title,
            fps=int(fps) if fps else 1,
            bitrate=float(cfg[mov]["bitrate"]) if "bitrate" in cfg[mov] else "500k",
            movie_filename=movie_filename,
            layout=cfg[mov]["layout"] if "layout" in cfg[mov] else "twoch-comp"
        ))
    return movie_def


def _read_channel_config(sec) -> Dict:
    out_dict = dict()
    try:
        for key, val in sec.items():
            if len(key) > 7 and key[:7] == "channel":
                _ch_keys = key.split("_")
                if len(_ch_keys) == 3:
                    k0, k1, k2 = _ch_keys
                    if k2 == "color":
                        if f"channel-{k1}" not in out_dict:
                            out_dict[f"channel-{k1}"] = dict()
                        _v = ast.literal_eval(val)
                        out_dict[f"channel-{k1}"][k2] = _v[:4]
                        out_dict[f"channel-{k1}"][f"color-name"] = _v[4]
                    elif k2 == "name":
                        if f"channel-{k1}" not in out_dict:
                            out_dict[f"channel-{k1}"] = dict()
                        out_dict[f"channel-{k1}"]["name"] = val
                    elif k2 == "histogram":
                        if val or val == "yes":
                            if f"overlays" not in out_dict:
                                out_dict[f"channel-{k1}"][f"overlays"] = list()
                            out_dict[f"channel-{k1}"]["overlays"].append("histogram")
    except Exception as e:
        log.error(e)

    return out_dict


def read_config_panel(cfg_path) -> List[ConfigPanel]:
    cfg, img_file, param_override, roi = _read_data_section(cfg_path)

    panel_headers = [s for s in cfg.sections() if s[:5].upper() == "PANEL"]
    if len(panel_headers) == 0:
        log.warning(f"No headers with name PANEL in file {cfg_path}.")
        return []

    # process PANEL sections
    panel_def = list()
    for pan in panel_headers:
        title = cfg[pan]["title"]
        filename = cfg[pan]["filename"]
        param_override = _process_overrides(cfg[pan], param_override, img_file)

        panel_def.append(ConfigPanel(
            header=pan,
            # series=int(cfg["DATA"]["series"]) if "series" in cfg["DATA"] else -1,
            series=img_file.series,
            frames=param_override.frames,
            channels=param_override.channels,
            zstacks=param_override.zstacks,
            scalebar=float(cfg[pan]["scalebar"]) if "scalebar" in cfg[pan] else 10,
            override_dt=param_override.dt,
            image_file=img_file,
            um_per_z=float(cfg["DATA"]["um_per_z"]) if "um_per_z" in cfg["DATA"] else img_file.um_per_z,
            columns=_rowcol_dict[cfg[pan]["columns"]],
            rows=_rowcol_dict[cfg[pan]["rows"]],
            channel_render_parameters=_read_channel_config(cfg[pan]),
            roi=roi,
            type=cfg[pan]["layout"] if "layout" in cfg[pan] else "all-frames",
            title=title,
            filename=filename,
            layout=cfg[pan]["layout"] if "layout" in cfg[pan] else "all-frames"
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
