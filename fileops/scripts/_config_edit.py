import configparser
from pathlib import Path
from typing import Callable, Optional

import pandas as pd
import typer
from typing_extensions import Annotated

from fileops.export.config import build_config_list
from fileops.logger import get_logger
from fileops.pathutils import guess_date_in_path
from fileops.scripts._config_latex_table import create_latex_table
from fileops.scripts._utils import _read_summary_list

log = get_logger(name='config_edit')


def generate_config_content(
        ini_path: Annotated[Path, typer.Argument(help="Path where config files are")],
        cfg_file_path: Annotated[Path, typer.Argument(help="Name of the file for the content of configuration files")],
        with_latex_table: Annotated[
            bool, typer.Option(help="Create a latex table with links to the output files")] = True,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
):
    """
    Create a summary of the content of config files
    """
    if progress_callback is not None:
        progress_callback(0, 0, "Reading configuration files...")
    df_cfg = build_config_list(ini_path, progress_callback=progress_callback)
    df_cfg = guess_date_in_path(df_cfg, date_col_name="session_fld")
    df_cfg.sort_values(by="cfg_folder")
    if progress_callback is not None:
        progress_callback(0, 0, "Saving configuration content spreadsheet...")
    df_cfg.to_excel(cfg_file_path, index=False)

    if with_latex_table:
        create_latex_table(cfg_file_path.parent / "cfg_table", df_cfg)


def generate_config_content_cli(
        ini_path: Annotated[Path, typer.Argument(help="Path where config files are")],
        cfg_file_path: Annotated[Path, typer.Argument(help="Name of the file for the content of configuration files")],
        with_latex_table: Annotated[
            bool, typer.Option(help="Create a latex table with links to the output files")] = True,
):
    """
    Create a summary of the content of config files
    """
    generate_config_content(ini_path, cfg_file_path, with_latex_table=with_latex_table)


def edit_config_content(
        cfg_file_path: Annotated[Path, typer.Argument(help="Name of the file for the content of configuration files")],
):
    """
    Update config files based on the content of input spreadsheet file
    """
    cdf = pd.read_excel(cfg_file_path).fillna("")

    for ix, row in cdf.iterrows():
        cfg = None
        try:
            path = row["cfg_path"]
            if len(path) == 0:
                continue
            cfg_path = Path(path)
            if not cfg_path.is_absolute():
                cfg_path = cfg_file_path.parent / cfg_path
            if not cfg_path.exists() or not cfg_path.is_file():
                log.warning(f"file {cfg_path} does not exist, skipping.")
            else:
                cfg = True

        except FileNotFoundError as e:
            import traceback
            log.error(e)
            log.error(traceback.format_exc())
        except Exception as e:
            import traceback
            log.error(e)
            log.error(traceback.format_exc())

        if cfg:
            cfgm = configparser.ConfigParser()
            cfgm.read(cfg_path)

            # Update section DATA
            cfgm.set("DATA", "image", row["image_path"].replace('%', '%%'))

            # Update section MOVIE
            cfgm.set("MOVIE", "title", row["title"].replace('%', '%%'))
            cfgm.set("MOVIE", "description", row["description"].replace('%', '%%'))
            cfgm.set("MOVIE", "fps", str(row["fps"]))
            cfgm.set("MOVIE", "layout", row["layout"])
            cfgm.set("MOVIE", "zstack", row["z_projection"])
            cfgm.set("MOVIE", "filename", row["movie_name"])
            cfgm.set("MOVIE", "bitrate", row["bitrate"])
            with open(cfg_path, "w") as configfile:
                cfgm.write(configfile)


def edit_config_paths_from_summary(
        summary_file_path: Annotated[Path, typer.Argument(help="Path where the summary spreadsheet file is")],
        cfg_file_path: Annotated[
            Path, typer.Argument(help="Path of spreadsheet where content of configuration files is")],
):
    """
    Update columns of configuration content spreadsheet based on summary file
    """
    if not summary_file_path.exists():
        raise ValueError("Path summary_file_path does not exist.")
    if not cfg_file_path.exists():
        raise ValueError("Path cfg_file_path does not exist.")

    # read
    dfs, dfsc = _read_summary_list(summary_file_path)
    cdf = pd.read_excel(cfg_file_path).fillna("")
    # update
    cdf["cfg_folder"] = dfs["cfg_folder"]
    cdf["cfg_path"] = dfs["cfg_path"]
    cdf.sort_values(by="cfg_folder")
    # save
    cdf.to_excel(cfg_file_path, index=False)
