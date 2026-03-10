import os
import re
import traceback
from pathlib import Path

import numpy as np
import pandas as pd
import typer
from typer import Typer
from typing_extensions import Annotated

from fileops.export.config import build_config_list
from fileops.image import MicroManagerFolderSeries
from fileops.image.factory import load_image_file
from fileops.logger import get_logger, silence_loggers
from fileops.scripts._utils import _read_summary_list

log = get_logger(name='summary')
app = Typer()

_iso8601_rgx = re.compile(r"[0-9]{8}")  # ISO 8601


def _guess_date(df: pd.DataFrame, date_col_name="folder") -> pd.DataFrame:
    def _d(r):
        s = str(r)
        m = re.search(_iso8601_rgx, s)
        if m:
            return s[m.start(): m.end()]
        return None

    df["date"] = df[date_col_name].apply(_d)
    # shift column 'date' to first position
    first_column = df.pop("date")
    df.insert(0, "date", first_column)

    return df


def relpath_from_date(s: str) -> str:
    p = Path(s)
    visited_lst = list()
    current_p = p
    while True:
        visited_lst.append(current_p.name)
        m = re.search(_iso8601_rgx, current_p.name)
        if m:
            return str(Path(*reversed(visited_lst)))
        else:
            current_p = current_p.parent


def _path_relative(path, relative_path) -> Path:
    try:
        path = Path(path)
        rel_path = path.relative_to(relative_path)
        return rel_path
    except ValueError:  # when relative_path is not in the subpath of path
        return path


@app.command()
def make(
        path: Annotated[Path, typer.Argument(help="Path from where to start the search")],
        path_csv: Annotated[Path, typer.Argument(help="Output path of the list")],
        relative_to: Annotated[Path, typer.Argument(help="All files will be relative to this path. "
                                                         "Otherwise, absolute path will be registered.")] = None,
        guess_date: Annotated[
            bool, typer.Option(
                help="Whether the script should extract the date from the file path. "
                     "It will only extract dates if they are in ISO 8601 format.")] = False,
):
    """
    Generate a summary list of microscope images stored in the specified path (recursively).
    The output is a comma separated values (CSV) file stored in path_csv.
    """

    out = pd.DataFrame()
    r = 1
    files_visited = []
    silence_loggers(loggers=["tifffile"], output_log_file="silenced.log")
    for root, directories, filenames in os.walk(path):
        for filename in filenames:
            joinf = 'No file specified yet'
            try:
                joinf = Path(root) / filename
                if joinf.suffix in (".png", ".xml"):
                    continue
                if joinf not in files_visited:
                    log.info(f'Processing {joinf.as_posix()}')
                    img_struc = load_image_file(joinf)
                    if img_struc is None:
                        continue
                    df_imf_info = (img_struc.info
                                   # .drop(columns=["timestamps"])
                                   .assign(cfg_path="", cfg_folder="")
                                   )
                    if relative_to is not None:
                        df_imf_info.loc[:, "folder"] = df_imf_info["folder"].apply(_path_relative, args=(relative_to,))
                    out = pd.concat([out, df_imf_info], ignore_index=True)
                    files_visited.extend([Path(root) / f for f in img_struc.files])
                    r += 1
                    if type(img_struc) == MicroManagerFolderSeries:  # all files in the folder are of the same series
                        break
            except FileNotFoundError as e:
                log.error(e)
                log.warning(f'Data not found in folder {root}.')
            except (IndexError, KeyError) as e:
                log.error(e)
                log.error(traceback.format_exc())
                log.warning(f'Data index/key not found in file; perhaps the file is truncated? (in file {joinf}).')
            except TypeError as e:
                log.error(f'Error trying to extract information of file {joinf}.')
                log.error(e)
            except BaseException as e:
                log.error(e)
                log.error(traceback.format_exc())
                raise e
    if guess_date:
        out = _guess_date(out)
    # change order of newly added columns to the beginning
    cols = list(out.columns)
    cols = cols[1::2] + cols[::2]
    out = out[cols]

    # generate an index
    out = out.reset_index(drop=True).reset_index().rename(columns={"index": "ix"})

    # simplify columns in out dataframe
    # change magnification in case it can be converted to it (no NaN values)
    if "magnification" in out and np.all(~out["magnification"].isna()):
        out.loc[:, "magnification"] = out["magnification"].astype(int)

    # check if pix_per_um is the same value for every tuple, write one value if so
    for col in ["pixel_size", "pix_per_um"]:
        ppm_tuple_check = out[col].apply(lambda t: isinstance(t, (list, tuple)) and len(t) == 2 and t[0] == t[1])
        if np.all(ppm_tuple_check):
            out.loc[:, col] = out[col].apply(lambda t: t[0])

    out.to_csv(path_csv, index=False)


def merge_column(df_merge: pd.DataFrame, column: str, use="x") -> pd.DataFrame:
    assert use in ["x", "y"]
    other_col = "y" if use == "x" else "x"

    _inf_as_na_opt = pd.options.mode.use_inf_as_na
    pd.options.mode.use_inf_as_na = True

    df_merge[f"{column}_x"] = np.where(df_merge[f"{column}_{use}"].notnull(), df_merge[f"{column}_{use}"],
                                       df_merge[f"{column}_{other_col}"])
    df_merge = df_merge.rename(columns={f"{column}_x": f"{column}"}).drop(columns=f"{column}_y")

    pd.options.mode.use_inf_as_na = _inf_as_na_opt
    return df_merge


@app.command()
def markdown(
        path: Annotated[Path, typer.Argument(help="Path of original list in Excel or OpenOffice's fods format")],
):
    """
    Export list of movie descriptions from microscopes to markdown format.
    """

    df = _read_summary_list(path)
    md_path = path.with_name(path.stem + ".md")
    df.to_markdown(md_path, index=False)


@app.command()
def merge(
        path_a: Annotated[Path, typer.Argument(help="Path of original list in Excel or OpenOffice's fods format")],
        path_b: Annotated[Path, typer.Argument(help="Path of list in CVS format with additional elements to be added")],
        path_out: Annotated[Path, typer.Argument(help="Output path of the list")],
        path_cfg: Annotated[Path, typer.Argument(help="Path where configuration files are in")] = None,
):
    """
    Merge two lists of microscopy movie descriptions updating with the data of the second list.

    """

    dfa = _read_summary_list(path_a)
    dfb = pd.read_csv(path_b, index_col=False).fillna('')

    for _df in [dfa, dfb]:
        # common_path = os.path.commonpath(_df["folder"].tolist())
        # _df["folder_rel"] = _df["folder"].apply(lambda p: os.path.relpath(p, common_path))
        _df["folder_rel"] = _df["folder"].apply(relpath_from_date)

    merge_cols = ["folder", "filename", "image_name"]
    if "image_id" in dfa.columns and "image_id" in dfb.columns:
        merge_cols.append("image_id")

    dfm = pd.merge(dfa, dfb, how="outer", on=merge_cols, indicator=True)
    for col in set(dfa.columns) - set(merge_cols):
        if col in dfa and col in dfb:
            dfm = merge_column(dfm, col, use="y")

    # update path of configuration files
    if not path_cfg:
        path_cfg = os.path.commonpath([p for p in dfm.loc[~dfm["cfg_path"].isna(), "cfg_path"] if p and p != "-"])
    df_cfg = build_config_list(path_cfg)[["cfg_path", "cfg_folder", "image"]]
    dfm["image"] = dfm["folder"] + "/" + dfm["filename"]

    merge_cols_cfg = ["image"]
    dfc = pd.merge(dfm.drop(columns="_merge"), df_cfg, how="left", on=merge_cols_cfg, indicator=True)
    for col in ["cfg_path", "cfg_folder"]:
        dfc = merge_column(dfc, col, use="y")

    dfo = dfc.drop(columns=["folder_rel", "image", "_merge"]).sort_values(by="ix")
    # path_out_outer = path_out.with_name(path_out.stem + "_outer" + path_out.suffix)
    dfo.to_csv(path_out, index=False)


if __name__ == "__main__":
    app()
