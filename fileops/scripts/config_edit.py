from pathlib import Path

import pandas as pd
import typer
from typing_extensions import Annotated

from fileops.export.config import build_config_list, read_config, ExportConfig, create_cfg_file
from fileops.logger import get_logger

log = get_logger(name='config_edit')
app = typer.Typer()


@app.command()
def generate(
        ini_path: Annotated[Path, typer.Argument(help="Path where config files are")],
        cfg_file_path: Annotated[Path, typer.Argument(help="Name of the file for the content of configuration files")],
):
    """
    Create a summary of the content of config files
    """
    df_cfg = build_config_list(ini_path)
    df_cfg.to_excel(cfg_file_path, index=False)


@app.command()
def edit(
        cfg_file_path: Annotated[Path, typer.Argument(help="Name of the file for the content of configuration files")],
):
    """
    Update config files based on the content of input spreadsheet file
    """
    cdf = pd.read_excel(cfg_file_path)

    for ix, row in cdf.iterrows():
        cfg = read_config(Path(row["cfg_path"]))
        create_cfg_file(path=Path(row["cfg_path"]),
                        contents={
                            "DATA":  {
                                "image":   Path(row["image"]),
                                "series":  cfg.series,
                                "channel": cfg.channels,
                                "frame":   "all"
                                # "frame":   cfg.frames
                            },
                            "MOVIE": {
                                "title":       row["title"],
                                "description": row["description"],
                                "fps":         row["fps"],
                                "layout":      row["layout"],
                                "zstack":      row["z_projection"],
                                "filename":    row["movie_name"]
                            }
                        })
