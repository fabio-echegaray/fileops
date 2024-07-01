import os
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import typer
from typer import Typer
from typing_extensions import Annotated

from fileops.export.config import create_cfg_file
from fileops.logger import get_logger
from fileops.pathutils import ensure_dir

log = get_logger(name='create_config')
app = Typer()


@app.command()
def generate(
        inp_path: Annotated[Path, typer.Argument(help="Path where the spreadsheet file is")],
        exp_path: Annotated[Path, typer.Argument(help="Path to export the config files")],
):
    """
    Generate config files dependent on the column cfg_folder of the input spreadsheet file
    """

    def _is_empty(r: pd.Series, col_name) -> bool:
        empty_float = type(r["cfg_path"]) == float and np.isnan(r["cfg_path"])
        empty_str = type(r["cfg_path"]) == str and len(r["cfg_path"]) == 0
        return empty_float or empty_str

    df = pd.read_excel(inp_path)

    for ix, r in df.iterrows():
        if r["cfg_path"] == "-":
            continue
        elif _is_empty(r, "cfg_path"):
            if not _is_empty(r, "cfg_folder"):
                log.debug(f"cfg_path empty but not the cfg_folder column ({r['cfg_folder']})")
                continue
            else:
                cfg_path = ensure_dir(exp_path / r["cfg_folder"]) / "export_definition.cfg"
                img_path = Path(r["folder"]) / r["filename"]
                cr_datetime = datetime.fromtimestamp(os.path.getmtime(img_path))

                log.info(f"creating {cfg_path}")
                create_cfg_file(path=cfg_path,
                                contents={
                                    "DATA":  {
                                        "image":   img_path.as_posix(),
                                        "series":  0,  # TODO: change
                                        "channel": [0, 1],  # TODO: change
                                        "frame":   "all"
                                    },
                                    "MOVIE": {
                                        "title":       "Lorem Ipsum",
                                        "description": "The story behind Lorem Ipsum",
                                        "fps":         10,
                                        "layout":      "twoch",
                                        "zstack":      "all-max",
                                        "filename":    f"{cr_datetime.strftime('%Y%m%d')}-"
                                                       f"{'-'.join(r['cfg_folder'].split('-')[1:])}"
                                    }
                                })
        else:
            cfg_path = Path(r["cfg_path"])

            if not cfg_path.exists():
                log.warning("Configuration path does not have a cfg file in it, but column cfg_path indicates it "
                            "should exist. This parameter is usually written down by an automated script, "
                            "check your source sheet, folder structure and update accordingly.\r\n"
                            f"{cfg_path.as_posix()}")
