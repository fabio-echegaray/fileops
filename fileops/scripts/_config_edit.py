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
from fileops.scripts._config_map import build_config_map
from fileops.scripts._schema import (
    CFG_CONTENT_SCHEMA_VERSION,
    SCHEMA_CFG_CONTENT,
    set_workbook_schema,
)

log = get_logger(name='config_edit')


def generate_config_content(
        ini_path: Annotated[Path, typer.Argument(help="Path where config files are")],
        cfg_file_path: Annotated[Path, typer.Argument(help="Name of the file for the content of configuration files")],
        with_latex_table: Annotated[
            bool, typer.Option(help="Create a latex table with links to the output files")] = True,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
):
    """
    Create a summary of the content of config files.

    The workbook carries the ``Content`` sheet (one row per MOVIE header) and
    the ``Configs`` registry (one row per config file).
    """
    if progress_callback is not None:
        progress_callback(0, 0, "Reading configuration files...")
    df_cfg = build_config_list(ini_path, progress_callback=progress_callback)
    df_cfg = guess_date_in_path(df_cfg, date_col_name="session_fld")
    df_cfg = df_cfg.sort_values(by="cfg_path")
    df_map = build_config_map(ini_path)
    if progress_callback is not None:
        progress_callback(0, 0, "Saving configuration content spreadsheet...")
    with pd.ExcelWriter(cfg_file_path, engine="openpyxl") as writer:
        df_cfg.to_excel(writer, sheet_name="Content", index=False)
        df_map.to_excel(writer, sheet_name="Configs", index=False)
        for sheet in writer.sheets.values():
            sheet.freeze_panes = "A2"
        set_workbook_schema(writer.book, SCHEMA_CFG_CONTENT, CFG_CONTENT_SCHEMA_VERSION)

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


def _select_movie_section(cfgm: configparser.ConfigParser, movie_name: str) -> Optional[str]:
    """Pick the MOVIE section to edit when a config has several.

    A config file may define more than one MOVIE section; the Content sheet has
    one row per MOVIE header, keyed by the ``movie_name`` (the MOVIE filename
    field). Match that when possible, otherwise fall back to the first section.
    """
    sections = [s for s in cfgm.sections() if s[:5].upper() == "MOVIE"]
    if not sections:
        return None
    if len(sections) == 1:
        return sections[0]
    for section in sections:
        if cfgm.get(section, "filename", fallback="") == movie_name:
            return section
    return sections[0]


def edit_config_content(
        cfg_file_path: Annotated[Path, typer.Argument(help="Name of the file for the content of configuration files")],
):
    """
    Update config files based on the content of input spreadsheet file
    """
    cdf = pd.read_excel(cfg_file_path, sheet_name="Content").fillna("")

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
            if "DATA" in cfgm:
                cfgm.set("DATA", "image", row["image_path"].replace('%', '%%'))

            # Update section MOVIE
            section = _select_movie_section(cfgm, row.get("movie_name", ""))
            if section is not None:
                cfgm.set(section, "title", row["title"].replace('%', '%%'))
                cfgm.set(section, "description", row["description"].replace('%', '%%'))
                cfgm.set(section, "fps", str(row["fps"]))
                cfgm.set(section, "layout", row["layout"])
                cfgm.set(section, "zstack", row["z_projection"])
                cfgm.set(section, "filename", row["movie_name"])
                cfgm.set(section, "bitrate", row["bitrate"])
            with open(cfg_path, "w") as configfile:
                cfgm.write(configfile)