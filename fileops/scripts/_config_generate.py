import ast
import os
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

import numpy as np
import pandas as pd
import typer
from typing_extensions import Annotated

from fileops.export.config import create_cfg_file
from fileops.logger import get_logger
from fileops.pathutils import ensure_dir
from fileops.scripts._config_map import read_config_map, relative_image_path
from fileops.scripts._utils import read_summary_list

log = get_logger(name='create_config')


def _coerce_series(value) -> int:
    try:
        if value is None or value == "" or (isinstance(value, float) and np.isnan(value)):
            return 0
        return int(float(value))
    except (ValueError, TypeError):
        return 0


def _registry_lookup(content_path: Path):
    """Return {key: (cfg_folder, existing_cfg_path)} from the Configs registry."""
    wanted: dict = {}
    existing: dict = {}
    if not content_path.exists():
        return wanted, existing
    reg = read_config_map(content_path)
    for _, r in reg.iterrows():
        key = (str(r["image_path"]), _coerce_series(r["image_series_id"]))
        cfg_folder = r.get("cfg_folder", "")
        cfg_path = r.get("cfg_path", "")
        if isinstance(cfg_folder, str) and cfg_folder.strip() not in ("", "-"):
            wanted[key] = cfg_folder
        if isinstance(cfg_path, str) and cfg_path.strip() not in ("", "-"):
            existing[key] = cfg_path
    return wanted, existing


def generate(
        inp_path: Annotated[Path, typer.Argument(help="Path where the summary spreadsheet file is")],
        exp_path: Annotated[Path, typer.Argument(help="Path to export the config files")],
        relative_to: Annotated[Path, typer.Option(help="Set to base where all paths should be relative to.")] = None,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        content_path: Optional[Path] = None,
):
    """
    Generate config files for the media rows that have a desired cfg_folder.

    The desired cfg_folder comes from the Configs registry (``cfg_content.xlsx``
    next to the summary by default); the media metadata (channel names, folder)
    is looked up live from the summary spreadsheet.
    """
    if not inp_path.exists():
        raise FileNotFoundError(f"File {inp_path} does not exist.")

    df, df_ch_info = read_summary_list(inp_path)

    if content_path is None:
        content_path = Path(inp_path).parent / "cfg_content.xlsx"
    wanted, existing = _registry_lookup(Path(content_path))

    def _summary_image_path(r) -> str:
        folder = Path(r["folder"])
        if not folder.is_absolute() and relative_to is not None:
            folder = Path(relative_to) / folder
        return relative_image_path((folder / r["filename"]).as_posix(), relative_to)

    df = df.copy()
    df["_cfg_path"] = [existing.get((_summary_image_path(r),
                                     _coerce_series(r["image_series_id"])
                                     if "image_series_id" in r.index else 0), "")
                       for _, r in df.iterrows()]

    total = len(df)
    for ix, r in df.iterrows():
        if progress_callback is not None:
            progress_callback(ix + 1, total, f"Creating configuration files... {ix + 1}/{total}")
        if r["_cfg_path"] == "-":
            continue
        key = (_summary_image_path(r),
               _coerce_series(r["image_series_id"]) if "image_series_id" in r.index else 0)
        if r["_cfg_path"]:
            cfg_path = Path(r["_cfg_path"])
            if not cfg_path.exists():
                log.warning("Configuration path does not have a cfg file in it, but the registry indicates it "
                            "should exist. Check your source sheet, folder structure and update accordingly. "
                            f"In {cfg_path.as_posix()}")
            continue

        cfg_folder = wanted.get(key, "")
        if not cfg_folder:
            log.debug("No cfg_folder in the Configs registry for this image; not creating a config file.")
            continue

        cfg_path = ensure_dir(Path(exp_path) / cfg_folder) / "export_definition.cfg"
        # folder is resolved for the file-system check while the (possibly
        # relative) form is kept for the "image" field written to the config.
        folder = Path(r["folder"])
        img_path = folder / r["filename"]
        img_path_abs = img_path if img_path.is_absolute() else Path(relative_to) / img_path if relative_to else img_path
        try:
            cr_datetime = datetime.fromtimestamp(os.path.getmtime(img_path_abs))
        except OSError:
            log.warning(f"Source image does not exist, skipping: {img_path_abs.as_posix()}")
            continue

        if cfg_path.exists():
            log.warning(f"Attempting to create a file that already exists: {cfg_path}")
            df.loc[ix, "_cfg_path"] = cfg_path.as_posix()
            continue

        log.info(f"creating {cfg_path}")
        file_movie_def = {
            "DATA":  {
                "image":   img_path.as_posix().replace("%", "%%"),
                "series":  int(r["image_id"].split(":")[1]),
                "channel": "all",
                "frame":   "all"
            },
            "MOVIE": {
                "title":       cfg_path,
                "description": "The story behind Lorem Ipsum",
                "fps":         10,
                "layout":      "two-col",
                "zstack":      "all-max",
                "filename":    f"{cfg_folder}-"
                               f"{cr_datetime.strftime('%Y%m%d')}-"
                               f"{r['image_id'].replace(':', '-')}"
            }
        }
        try:
            ch_names = ast.literal_eval(r["channel_names"])
            for k, ch in enumerate(ch_names):
                color = df_ch_info[df_ch_info["name"] == ch]["color"].tolist()[0]
                file_movie_def.update({f"CHANNEL-{k + 1:02d}": {
                    "name":  ch,
                    "color": color,
                }})
        except (SyntaxError, ValueError, KeyError, IndexError):  # possibly because there's no channel data
            log.warning("No channel data while exporting config file.")
        create_cfg_file(path=cfg_path, contents=file_movie_def)
        df.loc[ix, "_cfg_path"] = cfg_path.as_posix()

    return df.drop(columns=["_cfg_path"])


def generate_cli(
        inp_path: Annotated[Path, typer.Argument(help="Path where the summary spreadsheet file is")],
        exp_path: Annotated[Path, typer.Argument(help="Path to export the config files")],
        relative_to: Annotated[Path, typer.Option(help="Set to base where all paths should be relative to.")] = None,
):
    """
    Generate config files based on the cfg_folder column of the Configs registry.
    """
    generate(inp_path, exp_path, relative_to=relative_to)