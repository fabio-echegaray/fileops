import configparser
import copy
import os
import pandas as pd
import re
from dataclasses import dataclass
from pathlib import Path
from pytrackmate import trackmate_peak_import
from roifile import ImagejRoi
from typing import List, Dict, Union
from typing import NamedTuple

import fileops
from fileops.export.config_channel_section import update_channel_config_with_section_overrides
from fileops.export.config_data_section import read_data_section
from fileops.export.config_sections import process_overrides_of_section
from fileops.image import ImageFile
from fileops.logger import get_logger
from fileops.pathutils import ensure_dir
from fileops.plugins import HeaderReaderPlugin

log = get_logger(name='export')


# ----------------------------------------------------------------------------------------------------------------------
#  routines for handling of configuration files
# ----------------------------------------------------------------------------------------------------------------------
class ConfigCopyright(NamedTuple):
    author: str
    license: str
    license_file: Path | None


class ConfigVolume(NamedTuple):
    header: str
    configfile: Path
    series: int
    frames: List[int]
    channels: List[int]
    image_file: Union[ImageFile, None]
    roi: ImagejRoi
    crop: ImagejRoi | List[ImagejRoi]
    um_per_z: float
    filename: str


class ConfigProjection(NamedTuple):
    header: str
    configfile: Path
    series: int
    frames: List[int]
    channels: List[int]
    zstack_fn: str
    image_file: Union[ImageFile, None]
    roi: ImagejRoi
    bleach_correction: bool
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
    image_file: ImageFile
    path: Union[Path, None]
    name: Union[str, None]
    tracks: List[ConfigTrack]
    projections: List[ConfigProjection]
    copyright: ConfigCopyright


# ----------------------------------------------------------------------------------------------------------------------
#  routines for reading configuration files and headers
# ----------------------------------------------------------------------------------------------------------------------
def read_config(cfg_path: Path, with_root_path: Path | None = None) -> ExportConfig:
    cfg_path = cfg_path.absolute()
    if not cfg_path.exists():
        raise FileNotFoundError(f"Configuration file {cfg_path} does not exist!")
    cfg = configparser.ConfigParser()
    cfg.read(cfg_path)

    if "DATA" not in cfg:
        raise SyntaxError(f"No header DATA in file {cfg_path}.")

    cfg, img_file, param_override, roi = read_data_section(cfg_path, with_root_path=with_root_path)
    cfg_copyright = read_config_copyright(cfg_path, cfg)
    cfg_projections = read_config_projections(cfg_path, cfg, img_file, param_override, roi)
    cfg_tracks = read_config_tracks(cfg_path, cfg)

    exp_config = ExportConfig(
        config_file=cfg,
        image_file=img_file,
        path=cfg_path.parent,
        name=cfg_path.name,
        tracks=cfg_tracks,
        projections=cfg_projections,
        copyright=cfg_copyright
    )

    for p in fileops.config_type_plugins:
        # log.debug(f"Checking {p.name}")
        t_name = p.name
        header_reader_name = f"{t_name}_header_reader"
        for h in fileops.header_reader_plugins:
            if h.name == header_reader_name:
                # log.debug(f"Loading {header_reader_name}")
                clz = h.load()
                if not issubclass(clz, HeaderReaderPlugin):
                    continue
                cinst = clz(cfg_path, root_path=with_root_path)
                if cinst.has_valid_header():
                    attr_name = t_name + "s"
                    if hasattr(exp_config, attr_name):
                        attr = getattr(exp_config, attr_name)
                        if type(attr) is not List:
                            raise ValueError
                        setattr(exp_config, attr_name, attr + cinst.process())
                    else:
                        setattr(exp_config, attr_name, cinst.process())

    return exp_config


def read_config_copyright(cfg_path, cfg) -> ConfigCopyright | None:
    panel_copyright = [s for s in cfg.sections() if s.startswith("COPYRIGHT")]
    if len(panel_copyright) == 0:
        log.warning(f"No headers with name COPYRIGHT in file {cfg_path}.")
        return None
    elif len(panel_copyright) > 1:
        log.warning(f"Too many headers with name COPYRIGHT in file {cfg_path}.")
        return None

    # process COPYRIGHT section
    cp = cfg["COPYRIGHT"]

    return ConfigCopyright(
        author=cp["author"] if "author" in cp else "author unknown",
        license=cp["license"] if "license" in cp else "all rights reserved" if "author" in cp else "public domain",
        license_file=Path(cp["license_file"]) if "license_file" in cp else None
    )


def read_config_tracks(cfg_path, cfg) -> List[ConfigTrack]:
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


def read_config_projections(cfg_path, cfg, img_file, param_override, roi) -> List[ConfigProjection]:
    sec_projections = [s for s in cfg.sections() if s.startswith("PROJECTION")]
    if len(sec_projections) == 0:
        log.warning(f"No headers with name PROJECTION in file {cfg_path}.")
        return []

    # process PROJECTION sections
    prj_def = list()
    for prj in sec_projections:
        sec_param_override = process_overrides_of_section(cfg[prj], copy.deepcopy(param_override), img_file)
        sec_param_override = update_channel_config_with_section_overrides(sec_param_override, cfg[prj])

        prj_def.append(ConfigProjection(
            header=prj,
            configfile=cfg_path,
            series=img_file.series,
            frames=sec_param_override.frames,
            channels=sec_param_override.channels,
            zstack_fn=cfg[prj]["zstack_fn"] if "zstack_fn" in cfg[prj] else "all-max",
            image_file=img_file,
            roi=roi,
            bleach_correction=cfg[prj]["bleach_correction"]
            if "bleach_correction" in cfg[prj] and cfg[prj]["bleach_correction"] == "yes" else False,
            filename=cfg[prj]["filename"] if "filename" in cfg[prj] else "no_filename_given"

        ))
    return prj_def


_rowcol_dict = {
    "channel":  "channel",
    "channels": "channel",
    "frame":    "frame",
    "frames":   "frame"
}


# ----------------------------------------------------------------------------------------------------------------------
#  routines for checking if the output of configuration files exists
# ----------------------------------------------------------------------------------------------------------------------
def check_if_output_files_are_created(cfg_path: Path, with_root_path: Path | None = None) -> Dict:
    out = {"none": False}  # return object is a dictionary of all headers and a boolean value
    cfg_path = cfg_path.absolute()
    if not cfg_path.exists():
        raise FileNotFoundError(f"Configuration file {cfg_path} does not exist!")
    cfg = configparser.ConfigParser()
    cfg.read(cfg_path)

    headers = [s for s in cfg.sections() if s.upper().startswith("PROJECTION")]
    if len(headers) == 0:
        log.warning(f"No headers with name PROJECTION to check in file {cfg_path}.")
    else:
        # process PROJECTION sections
        _out = {mvh: False for mvh in headers}
        for mov in headers:
            if "filename" in cfg[mov]:
                out_path = Path(cfg[mov]["filename"])
                if out_path.exists():
                    out[mov] = True
        out.update(_out)  # add new headers

    # check plugins
    for p in fileops.config_type_plugins:
        # log.debug(f"Checking {p.name}")
        t_name = p.name
        header_reader_name = f"{t_name}_header_reader"
        for h in fileops.header_reader_plugins:
            if h.name == header_reader_name:
                # log.debug(f"Loading {header_reader_name}")
                clz = h.load()
                if not issubclass(clz, HeaderReaderPlugin):
                    continue
                cinst = clz(cfg_path, root_path=with_root_path)
                if cinst.has_valid_header():
                    out.update(cinst.header_output_file_exist())

    out.pop("none")
    return out


# ----------------------------------------------------------------------------------------------------------------------
#  routines for creating configuration files and lists of them thereof
# ----------------------------------------------------------------------------------------------------------------------
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
        inc_m = None

        # iterate through sections starting with "MOVIE"
        headers = [s for s in cfg.sections() if s[:5].upper() == "MOVIE"]
        for mov in headers:
            out_name = (f.parent / (cfg[mov]["filename"] + ".mp4")) if "filename" in cfg[mov] else None

            col = re.search(r'([0-9]+)hr collection', cfg[mov]["description"])
            inc = re.search(r'([0-9:]+)(hr)? incubation', cfg[mov]["description"])

            col_m = int(col.groups()[0]) * 60 if col else None
            if inc:
                if ":" in inc.groups()[0]:
                    hr, min = inc.groups()[0].split(":")
                    inc_m = int(hr) * 60 + int(min)
                else:
                    inc_m = int(inc.groups()[0]) * 60

            # now append the data collected
            img_path = Path(cfg["DATA"]["image"])
            dfl.append({
                "cfg_path":       f.as_posix(),
                "cfg_folder":     f.parent.name,
                "movie_name":     cfg[mov]["filename"] if "filename" in _read_cfg_file(f)[mov] else "",
                "image_filename": img_path.name,
                "image_path":     img_path.absolute().as_posix(),
                "output_path":    out_name,
                "image_series":   int(cfg["DATA"]["series"] if "series" in cfg["DATA"] else 0),
                "session_fld":    img_path.parent.parent.name,
                "img_fld":        img_path.parent.name,
                "title":          cfg[mov]["title"],
                "description":    cfg[mov]["description"],
                "bitrate":        cfg[mov]["bitrate"] if "bitrate" in cfg[mov] else "500k",
                "t_collection":   col_m,
                "t_incubation":   inc_m,
                "fps":            cfg[mov]["fps"] if "fps" in cfg[mov] else 10,
                "layout":         cfg[mov]["layout"] if "layout" in cfg[mov] else "twoch-comp",
                "z_projection":   cfg[mov]["z_projection"] if "z_projection" in cfg[mov] else "all-max",
            })

    df = pd.DataFrame(dfl)
    return df
