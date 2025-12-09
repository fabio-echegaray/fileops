import configparser
import copy
import os
import re
from pathlib import Path
from typing import List, Dict, Union, Iterable, Tuple
from typing import NamedTuple

import pandas as pd
from pytrackmate import trackmate_peak_import
from roifile import ImagejRoi

from fileops.export._param_override import ParameterOverride
from fileops.image import ImageFile
from fileops.image.factory import load_image_file
from fileops.logger import get_logger
from fileops.pathutils import ensure_dir

log = get_logger(name='export')


# ----------------------------------------------------------------------------------------------------------------------
#  routine that imports a package from a string definition
# ----------------------------------------------------------------------------------------------------------------------
def _import(name):
    components = name.split('.')
    mod = __import__(components[0])
    for comp in components[1:]:
        mod = getattr(mod, comp)
    return mod


# ----------------------------------------------------------------------------------------------------------------------
#  routines for handling of configuration files
# ------------------------------------------------------------------------------------------------------------------
class ConfigMovie(NamedTuple):
    header: str
    configfile: Path
    series: int
    frames: Iterable[int]
    channels: List[int]
    channel_render_parameters: Dict
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
    include_tracks: Union[str, bool]


class ConfigPanel(NamedTuple):
    header: str
    configfile: Path
    series: int
    frames: List[int]
    channels: List[int]
    channel_render_parameters: Dict
    zstacks: List[int]
    scalebar: float
    override_dt: Union[float, None]
    image_file: Union[ImageFile, None]
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


class ExportConfig(NamedTuple):
    config_file: configparser.ConfigParser
    path: Union[Path, None]
    name: Union[str, None]
    movies: List[ConfigMovie]
    panels: List[ConfigPanel]
    tracks: List[ConfigTrack]


def _process_overrides_of_section(section, param_override, img_file: ImageFile):
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
                param_override.frames = range(int(_f[0]), int(_f[1]) + 1)
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


def _read_data_section(cfg_path) -> Tuple[configparser.ConfigParser, ImageFile, ParameterOverride, ImagejRoi]:
    cfg = configparser.ConfigParser()
    cfg.read(cfg_path)

    assert "DATA" in cfg, f"No header DATA in file {cfg_path}."

    img_path = Path(cfg["DATA"]["image"])
    if not img_path.is_absolute():
        img_path = cfg_path.parent / img_path
    if not img_path.exists():
        raise FileNotFoundError(f"Image file {img_path} does not exist.")
    kwargs = {
        "override_dt": cfg["DATA"]["override_dt"] if "override_dt" in cfg["DATA"] else None,
    }
    if "series" in cfg["DATA"]:
        series_n = int(cfg["DATA"]["series"])
        kwargs.update(dict(image_series=series_n - 1))

    if "use_loader_class" in cfg["DATA"]:
        _cls = _import(f"{cfg['DATA']['use_loader_class']}")
        img_file: ImageFile = _cls(img_path, **kwargs)
    else:
        img_file = load_image_file(img_path, **kwargs)
    assert img_file, f"Error loading image file {img_path}."

    param_override = _process_overrides_of_section(cfg["DATA"], ParameterOverride(img_file), img_file)
    param_override = _update_overrides_from_channel_sections(param_override, cfg_path)

    # process ROI path
    roi = None
    if "ROI" in cfg["DATA"]:
        roi_path = Path(cfg["DATA"]["ROI"])
        if not roi_path.is_absolute():
            roi_path = cfg_path.parent / roi_path
            roi = ImagejRoi.fromfile(roi_path)

    return cfg, img_file, param_override, roi


def _update_overrides_from_channel_sections(param_override: ParameterOverride, cfg_path) -> ParameterOverride:
    cfg = configparser.ConfigParser()
    cfg.read(cfg_path)

    ch_sections = [s for s in cfg.sections() if "CHANNEL" in s]
    if len(ch_sections) == 0:
        log.info(f"No CHANNEL header in file {cfg_path}.")
        # generate default channel configuration
        for ch_num in param_override.channels:
            param_override.channel_info = (ch_num, dict(name=f"ch-{ch_num:02d}"))  # value has to be a tuple (key, dict)

        return param_override

    for ch_sec in ch_sections:
        ch_num = int(ch_sec.split("-")[1])
        section_data = cfg[ch_sec]
        # ch_key at this level is 1-indexed, but for at the level of ParameterOverride it's 0-indexed
        param_override.channel_info = (ch_num - 1, dict(section_data.items()))  # value has to be a tuple (key, dict)

    return param_override


def read_config(cfg_path: Path) -> ExportConfig:
    cfg_path = cfg_path.absolute()
    if not cfg_path.exists():
        raise FileNotFoundError(f"Configuration file {cfg_path} does not exist!")
    cfg = configparser.ConfigParser()
    cfg.read(cfg_path)

    if "DATA" not in cfg:
        raise SyntaxError(f"No header DATA in file {cfg_path}.")

    cfg_movie = read_config_movie(cfg_path)
    cfg_panel = read_config_panel(cfg_path)
    cfg_tracks = read_config_tracks(cfg_path)

    return ExportConfig(
        config_file=cfg,
        path=cfg_path.parent,
        name=cfg_path.name,
        movies=cfg_movie,
        panels=cfg_panel,
        tracks=cfg_tracks
    )


def read_config_movie(cfg_path) -> List[ConfigMovie]:
    cfg, img_file, param_override, roi = _read_data_section(cfg_path)

    movie_headers = [s for s in cfg.sections() if s[:5].upper() == "MOVIE"]
    if len(movie_headers) == 0:
        log.debug(f"No headers of type MOVIE in file {cfg_path}.")
        return []

    # process MOVIE sections
    movie_def = list()
    for mov in movie_headers:
        title = cfg[mov]["title"]
        fps = cfg[mov]["fps"]
        movie_filename = cfg[mov]["filename"]
        sec_param_override = _process_overrides_of_section(cfg[mov], copy.deepcopy(param_override), img_file)
        sec_param_override = _update_channel_config_with_section_overrides(sec_param_override, cfg[mov])
        include_tracks = cfg[mov]["include_tracks"] if "include_tracks" in cfg[mov] else None

        movie_def.append(ConfigMovie(
            header=mov,
            configfile=cfg_path,
            series=img_file.series,
            frames=sec_param_override.frames,
            channels=sec_param_override.channels,
            channel_render_parameters=sec_param_override.channel_info,
            scalebar=float(cfg[mov]["scalebar"]) if "scalebar" in cfg[mov] else None,
            override_dt=sec_param_override.dt,
            image_file=img_file,
            zstack_fn=cfg[mov]["zstack_fn"] if "zstack_fn" in cfg[mov] else "all-max",
            um_per_z=float(cfg["DATA"]["um_per_z"]) if "um_per_z" in cfg["DATA"] else img_file.um_per_z,
            roi=roi,
            title=title,
            fps=int(fps) if fps else 1,
            bitrate=cfg[mov]["bitrate"] if "bitrate" in cfg[mov] else "500k",
            movie_filename=movie_filename,
            layout=cfg[mov]["layout"] if "layout" in cfg[mov] else "twoch-comp",
            include_tracks=(
                include_tracks if type(include_tracks) is bool
                else include_tracks == "yes" if type(include_tracks) is str
                else False
            )
        ))
    return movie_def


def _update_channel_config_with_section_overrides(param_override: ParameterOverride, sec) -> ParameterOverride:
    for key, val in sec.items():
        try:
            if len(key) > 7 and key[:7] == "channel":
                _ch_keys = key.split("_")
                if len(_ch_keys) == 3:
                    k0, k1, k2 = _ch_keys
                    # channel number validation
                    ch_num = int(k1)
                    if ch_num < 1:
                        raise KeyError(f"Channel number in configuration file starts from 1.")
                    if k2 in ("color", "colour", "name", "histogram",):
                        # ParameterOverride is 0-indexed
                        param_override.channel_info = (ch_num - 1, {k2: val})  # value has to be a tuple (key, dict)
        except Exception as e:
            log.error(e)

    return param_override


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
        sec_param_override = _process_overrides_of_section(cfg[pan], copy.deepcopy(param_override), img_file)
        sec_param_override = _update_channel_config_with_section_overrides(sec_param_override, cfg[pan])

        if len(sec_param_override.frames) == 0:
            raise ValueError(f"No frames to render in panel section {pan}.")

        panel_def.append(ConfigPanel(
            header=pan,
            configfile=cfg_path,
            # series=int(cfg["DATA"]["series"]) if "series" in cfg["DATA"] else -1,
            series=img_file.series,
            frames=sec_param_override.frames,
            channels=sec_param_override.channels,
            channel_render_parameters=sec_param_override.channel_info,
            zstacks=sec_param_override.zstacks,
            scalebar=float(cfg[pan]["scalebar"]) if "scalebar" in cfg[pan] else 10,
            override_dt=sec_param_override.dt,
            image_file=img_file,
            um_per_z=float(cfg["DATA"]["um_per_z"]) if "um_per_z" in cfg["DATA"] else img_file.um_per_z,
            columns=_rowcol_dict[cfg[pan]["columns"]],
            rows=_rowcol_dict[cfg[pan]["rows"]],
            roi=roi,
            type=cfg[pan]["layout"] if "layout" in cfg[pan] else "all-frames",
            title=title,
            filename=filename,
            layout=cfg[pan]["layout"] if "layout" in cfg[pan] else "all-frames"
        ))
    return panel_def


def read_config_tracks(cfg_path) -> List[ConfigTrack]:
    cfg, img_file, param_override, roi = _read_data_section(cfg_path)

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
