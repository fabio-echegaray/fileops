import os
import traceback
from pathlib import Path
from typing import Callable, Optional

import numpy as np
import pandas as pd
import typer
from pydantic import ValidationError
from typer import Typer
from typing_extensions import Annotated

from fileops.export.config import build_config_list
from fileops.image import MicroManagerFolderSeries
from fileops.image.factory import load_image_file
from fileops.logger import get_logger
from fileops.pathutils import guess_date_in_path, relpath_from_date
from fileops.scripts._config_duplicates import check_duplicates
from fileops.scripts._utils import _read_summary_list, path_relative

log = get_logger(name='summary')
app = Typer()

_blackliset_suffixes = [".png", ".xml", ".mp4", ".avi", ".cfg", ".txt", ".log", ".py", ".pvsm"]

__columns_reordered__ = [
    "ix",
    "cfg_folder",
    "cfg_path",
    "folder",
    "filename",
    "frames",
    "channels",
    "z-stacks",
    "height",
    "width",
    "delta_t",
    "data_type",
    "magnification",
    "pix_per_um",
    "pixel_size",
    "z_step_size",
    "pixel_size_unit",
    "z_step_size_unit",
    "channel_names",
    "image_name",
    "image_id",
    "image_series_id",
    "instrument_id",
    "pixels_id",
    "objective_id",
    "date",
    "acquisition",
    "most recent modification",
    "change (Unix), creation (Windows)",
]


def make(
        path: Path,
        path_csv: Path,
        relative_to: Path = None,
        guess_date: bool = False,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
):
    """
    Generate a summary list of microscope images stored in the specified path (recursively).
    The output is a comma separated values (CSV) file stored in path_csv.
    """

    out = pd.DataFrame()
    out_ch = pd.DataFrame()
    cols_to_match = ["name", "nd_filter", "pinhole_size", "acquisition_mode", "contrast_method",
                     "excitation_wavelength", "illumination_type"]
    r = 1
    files_visited = []
    processed = 0
    for root, directories, filenames in os.walk(path):
        for filename in filenames:
            joinf = 'No file specified yet'
            try:
                joinf = Path(root) / filename
                if joinf.suffix in _blackliset_suffixes:
                    continue
                if joinf not in files_visited:
                    processed += 1
                    if progress_callback is not None:
                        progress_callback(processed, 0, f"Reading {joinf.as_posix()}")
                    log.info(f'Processing {joinf.as_posix()}')
                    img_struc = load_image_file(joinf)
                    if img_struc is None:
                        continue
                    df_imf_info = img_struc.info

                    if relative_to is not None:
                        df_imf_info = path_relative(df_imf_info, relative_to, path_columns=["folder", ])
                    out = pd.concat([out, df_imf_info], ignore_index=True)
                    df_imf_channels = img_struc.info_channels
                    out_ch = pd.concat([out_ch, df_imf_channels], ignore_index=True)
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
            except ValidationError as e:
                log.error(f'Error validating file {joinf}.')
                log.error(e)
            except Exception as e:
                log.error(e)
                log.error(traceback.format_exc())
                raise e
    if len(out) == 0:
        # no supported image files were found; produce an empty summary instead of crashing
        out = pd.DataFrame(columns=[c for c in __columns_reordered__ if c != "ix"])
        out_ch = pd.DataFrame(columns=cols_to_match + ["id"])
        log.warning(f"No supported image files found in {path}. An empty summary was created.")

    if guess_date:
        out = guess_date_in_path(out)

    # create cfg_path and cfg_folder columns
    out = out.assign(cfg_path="", cfg_folder="")
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

    # reorder columns
    df_set = set(out.columns)
    ro_set = set(__columns_reordered__)
    # check if there are columns not generated in df creation (e.g. 'date' when inferred dates is set)
    if len(diff_set_1 := (ro_set - df_set)) > 0:
        for c in diff_set_1:
            __columns_reordered__.remove(c)
    elif len(diff_set_2 := (df_set - ro_set)) > 0:
        log.warning(f"Not all columns are saved.\n"
                    f"Columns not included in the spreadsheet: {diff_set_2}.")
    out = out[__columns_reordered__]

    out.to_csv(path_csv, index=False)

    # ------------------------------------------------------------------------------------------------------------------
    # save excel file
    # ------------------------------------------------------------------------------------------------------------------
    # process channel data to drop redundant rows (most experiments use the same channel data)
    out_ch = (out_ch.drop_duplicates(subset=cols_to_match, ignore_index=True)
              .drop(columns="id"))

    if progress_callback is not None:
        progress_callback(processed, 0, "Saving summary spreadsheet...")

    # save information to different sheets in excel file
    with pd.ExcelWriter(path_csv.parent / f"{path_csv.name}.xlsx", engine="openpyxl") as writer:
        out_ch.to_excel(writer, sheet_name="Channels", index=False)
        if len(out) > 0:
            out.query("frames==1").to_excel(writer, sheet_name="Files-Stills", index=False)
            out.query("frames>1").to_excel(writer, sheet_name="Files-Timeseries", index=False)
            writer.book.active = writer.book["Files-Timeseries"]  # Set Active Sheet


@app.command("make")
def make_cli(
        path: Annotated[Path, typer.Argument(help="Path from where to start the search")],
        path_csv: Annotated[Path, typer.Argument(help="Output path of the list")],
        relative_to: Annotated[Path, typer.Option(help="All files will be relative to this path. "
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
    make(path, path_csv, relative_to=relative_to, guess_date=guess_date)


def merge_column(df_merge: pd.DataFrame, column: str, use="x") -> pd.DataFrame:
    """
    merges two columns 'x' and 'y' into one without suffixes
    :param df_merge: dataframe where columns to be merged reside
    :param column: the name of the column whose copies 'x' and 'y' will be extracted to
    :param use: column to prefer values from
    :return: dataframe with columns <column>_x and <column>_y merged into <column>
    """
    assert use in ["x", "y"]
    if f"{column}_x" not in df_merge or f"{column}_y" not in df_merge:
        return df_merge
    other_col = "y" if use == "x" else "x"

    valid = (df_merge[f"{column}_{use}"].notnull() &
             ~np.isinf(pd.to_numeric(df_merge[f"{column}_{use}"], errors="coerce")))
    df_merge[f"{column}_x"] = np.where(valid, df_merge[f"{column}_{use}"],
                                       df_merge[f"{column}_{other_col}"])
    df_merge = df_merge.rename(columns={f"{column}_x": f"{column}"}).drop(columns=f"{column}_y")
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


def update_from_cfg_folder(
        path_summary: Path,
        path_cfg: Path,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
):
    """
    Update the columns cfg_path and cfg_folder of microscopy movie descriptions from the folder where the cfg files are.

    """
    if not path_summary.exists():
        raise ValueError("Path path_summary does not exist.")
    if not path_cfg.exists():
        raise ValueError("Path path_cfg does not exist.")

    if progress_callback is not None:
        progress_callback(0, 0, "Scanning configuration files...")
    dfc = build_config_list(path_cfg)
    if len(dfc) == 0:
        log.info(f"No configuration files in folder {path_cfg}.")
        return

    # FIXME: Nikon images are not generating image_series_id
    dfc["img_ser"] = dfc["image_path"] + "|" + dfc["image_series_id"].astype(str)
    check_duplicates(dfc, "img_ser", path_summary)

    dfs, dfsc = _read_summary_list(path_summary)
    check_duplicates(dfs, "cfg_folder", path_summary)

    if progress_callback is not None:
        progress_callback(0, 0, "Updating summary with configuration folders...")

    dfs["image_path"] = dfs["folder"] + "/" + dfs["filename"]
    dfc.rename(columns={"image_series": "image_series_id"}, inplace=True)
    dfm = dfc.merge(dfs, how="outer", left_on=["image_path", "image_series_id"],
                    right_on=["image_path", "image_series_id"])

    for col in ["cfg_path", "cfg_folder"]:
        dfm = merge_column(dfm, col, use="y")

    dfm.dropna(subset=["image_series_id"], inplace=True)
    dfm["image_series_id"] = dfm["image_series_id"].astype(int)

    dfm = (
        dfm.loc[:, dfs.columns]
        .drop(columns=["ix", "image_path"])
        .reset_index()
        .rename(columns={"index": "ix"})
    )

    if progress_callback is not None:
        progress_callback(0, 0, "Saving updated summary spreadsheet...")

    # save timeseries and stills data to excel file
    with pd.ExcelWriter(path_summary, engine="openpyxl", mode='a', engine_kwargs={'keep_vba': True}) as writer:
        wb = writer.book
        for sheet in ["Files-Timeseries", "Files-Stills"]:
            try:
                wb.remove(wb[sheet])
            except KeyError:
                pass

        dfm.query("frames > 1").to_excel(writer, sheet_name="Files-Timeseries", index=False)
        dfm.query("frames == 1").to_excel(writer, sheet_name="Files-Stills", index=False)


@app.command("update-from-cfg-folder")
def update_from_cfg_folder_cli(
        path_summary: Annotated[Path, typer.Argument(help="Path of summary list in Excel or OpenOffice's fods format")],
        path_cfg: Annotated[Path, typer.Argument(help="Path where configuration files are in")],
):
    """
    Update the columns cfg_path and cfg_folder of microscopy movie descriptions from the folder where the cfg files are.
    """
    update_from_cfg_folder(path_summary, path_cfg)


if __name__ == "__main__":
    app()
