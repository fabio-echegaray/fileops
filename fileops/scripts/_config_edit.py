import configparser
from pathlib import Path

import pandas as pd
import typer
from typing_extensions import Annotated

from fileops.export.config import build_config_list, read_config
from fileops.logger import get_logger
from fileops.scripts.summary import _guess_date

log = get_logger(name='config_edit')


def generate_config_content(
        ini_path: Annotated[Path, typer.Argument(help="Path where config files are")],
        cfg_file_path: Annotated[Path, typer.Argument(help="Name of the file for the content of configuration files")],
):
    """
    Create a summary of the content of config files
    """
    df_cfg = build_config_list(ini_path)
    df_cfg = _guess_date(df_cfg, date_col_name="img_fld")
    df_cfg.to_excel(cfg_file_path, index=False)


def edit_config_content(
        cfg_file_path: Annotated[Path, typer.Argument(help="Name of the file for the content of configuration files")],
):
    """
    Update config files based on the content of input spreadsheet file
    """
    cdf = pd.read_excel(cfg_file_path)

    for ix, row in cdf.iterrows():
        cfg = None
        try:
            cfg_path = Path(row["cfg_path"])
            if not cfg_path.exists():
                log.warning(f"file {cfg_path} does not exist. Skipping.")
            cfg = read_config(cfg_path)
        except Exception as e:
            import traceback
            log.error(e)
            log.error(traceback.format_exc())

        if cfg:
            cfgm = configparser.ConfigParser()
            cfgm.read(cfg_path)

            # Update section MOVIE
            cfgm.set("MOVIE", "title", row["title"].replace('%', '%%'))
            cfgm.set("MOVIE", "description", row["description"].replace('%', '%%'))
            cfgm.set("MOVIE", "fps", str(row["fps"]))
            cfgm.set("MOVIE", "layout", row["layout"])
            cfgm.set("MOVIE", "zstack", row["z_projection"])
            cfgm.set("MOVIE", "bitrate", row["bitrate"])
            with open(cfg_path, "w") as configfile:
                cfgm.write(configfile)
