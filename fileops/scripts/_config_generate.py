import ast
import os
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import typer
from typing_extensions import Annotated

from fileops.export.config import create_cfg_file
from fileops.logger import get_logger
from fileops.pathutils import ensure_dir
from fileops.scripts._utils import _read_summary_list

log = get_logger(name='create_config')


def generate(
        inp_path: Annotated[Path, typer.Argument(help="Path where the summary spreadsheet file is")],
        exp_path: Annotated[Path, typer.Argument(help="Path to export the config files")],
):
    """
    Generate config files dependent on the column cfg_folder of the input spreadsheet file
    """

    def _is_empty(r: pd.Series, col_name) -> bool:
        empty_float = type(r[col_name]) == float and np.isnan(r[col_name])
        empty_str = type(r[col_name]) == str and len(r[col_name]) == 0
        return r[col_name] is None or empty_float or empty_str

    if not inp_path.exists():
        raise FileNotFoundError(f"File {inp_path} does not exist.")

    df, df_ch_info = _read_summary_list(inp_path)
    if not "cfg_path" in df:
        df["cfg_path"] = None
        # Move 'cfg_path' to the second position (index 1)
        column_to_move = df.pop('cfg_path')
        df.insert(1, 'cfg_path', column_to_move)

    for ix, r in df.iterrows():
        if r["cfg_path"] == "-":
            continue
        elif _is_empty(r, "cfg_path"):
            if _is_empty(r, "cfg_folder"):
                log.debug(f"Column cfg_path is empty but column cfg_folder is also empty. Can't create a file.")
                continue
            else:
                cfg_path = ensure_dir(exp_path / r["cfg_folder"]) / "export_definition.cfg"
                img_path = Path(r["folder"]) / r["filename"]
                cr_datetime = datetime.fromtimestamp(os.path.getmtime(img_path))

                if cfg_path.exists():
                    log.warning(f"Attempting to create a file that already exists: {cfg_path}")
                else:
                    log.info(f"creating {cfg_path}")
                    file_movie_def = {
                        "DATA":  {
                            "image":   img_path.as_posix().replace("%", "%%"),
                            "series":  int(r["image_id"].split(":")[1]),
                            "channel": "all",
                            "frame":   "all"
                        },
                        "MOVIE": {
                            "title":       "Lorem Ipsum",
                            "description": "The story behind Lorem Ipsum",
                            "fps":         10,
                            "layout":      "two-col",
                            "zstack":      "all-max",
                            "filename":    f"{r['cfg_folder']}-"
                                           f"{cr_datetime.strftime('%Y%m%d')}-"
                                           f"{r['image_id'].replace(':', '-')}"
                        }
                    }
                    ch_names = ast.literal_eval(r["channel_names"])
                    for k, ch in enumerate(ch_names):
                        color = df_ch_info[df_ch_info["name"] == ch]["color"].tolist()[0]
                        file_movie_def.update({f"CHANNEL-{k + 1:02d}": {
                            "name":  ch,
                            "color": color,
                        }})
                    create_cfg_file(path=cfg_path, contents=file_movie_def)
                    df.loc[ix, "cfg_path"] = cfg_path
        else:
            try:
                cfg_path = Path(r["cfg_path"])

                if not cfg_path.exists():
                    log.warning("Configuration path does not have a cfg file in it, but column cfg_path indicates it "
                                "should exist. This parameter is usually written down by an automated script, "
                                "check your source sheet, folder structure and update accordingly. "
                                f"In {cfg_path.as_posix()}")
                else:
                    df.loc[ix, "cfg_path"] = cfg_path
            except Exception as e:
                log.error(e)
    return df
