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
from fileops.pathutils import ensure_dir, guess_date_in_path, relpath_from_date
from fileops.scripts._config_duplicates import check_duplicates, DuplicateEntryError
from fileops.scripts._utils import read_summary_list, path_relative

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
    # pre-scan to count the candidate files, so progress can be reported as a fraction of a total.
    # The count is approximate: files that belong to an already visited series are skipped
    # without being counted as processed, and series folders stop the scan early.
    total = 0
    for root, directories, filenames in os.walk(path):
        total += sum(1 for filename in filenames if Path(filename).suffix not in _blackliset_suffixes)
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
                        progress_callback(processed, total, f"Reading {joinf.as_posix()}")
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
    out_ch = (out_ch
              .drop_duplicates(subset=cols_to_match, ignore_index=True)
              .drop(columns="id")
              .sort_values(by=[c for c in ["date", "session_fld", "img_fld", "image_series_id"] if c in out_ch.columns])
              )

    if progress_callback is not None:
        progress_callback(processed, total, "Saving summary spreadsheet...")

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

    df = read_summary_list(path)
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

    dfa = read_summary_list(path_a)
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


def _match_relative_cfg_by_suffix(dfc: pd.DataFrame, dfm: pd.DataFrame) -> pd.DataFrame:
    """Fallback for config files whose stored image path is relative.

    The exact merge above requires both sides to resolve to the same string,
    which only holds when both are anchored at the same base. When the summary
    image path is absolute (or anchored at a different base), the *stored*
    relative path still matches as a suffix of it, so the config folder can be
    located without guessing the shared base.
    """
    rel_cfg = dfc.loc[
        dfc["image_path_rel"].apply(lambda p: not Path(p).is_absolute()),
        ["image_path_rel", "image_series_id", "cfg_path", "cfg_folder"],
    ]
    unmatched = dfm["cfg_folder"].isna() & dfm["image_path"].notna()
    if len(rel_cfg) and unmatched.any():
        by_rel: dict = {}
        for _, c in rel_cfg.iterrows():
            by_rel.setdefault(c["image_path_rel"], []).append(c)
        for idx in dfm.index[unmatched]:
            img = dfm.at[idx, "image_path"]
            series = dfm.at[idx, "image_series_id"]
            hits = set()
            for rel, entries in by_rel.items():
                if not img.endswith("/" + rel):
                    continue
                for e in entries:
                    if e["image_series_id"] == series:
                        hits.add((e["cfg_path"], e["cfg_folder"]))
            if not hits:
                continue
            cfg_folders = {h[1] for h in hits}
            if len(cfg_folders) > 1:
                raise DuplicateEntryError(
                    "image series mapped to more than one configuration folder:\n"
                    f"{img} (series {int(series)}) -> {sorted(cfg_folders)}")
            cfg_path, cfg_folder = next(iter(hits))
            dfm.at[idx, "cfg_path"] = cfg_path
            dfm.at[idx, "cfg_folder"] = cfg_folder
    return dfm


def _drop_phantom_cfg_rows(dfm: pd.DataFrame) -> pd.DataFrame:
    """Drop merged rows whose config also matched a summary media row.

    Configs hanging off the media side of the outer merge (their resolved
    image_path differs from the summary's, so the merge keys never joined)
    still exist on the config side as well; drop those phantom rows so they do
    not also end up as media-less config entries. This covers both the suffix
    matches above and associations already present in the summary.
    """
    matched_cfg = set(dfm.loc[dfm["folder"].notna(), "cfg_path"].dropna())
    if matched_cfg:
        phantom = dfm["folder"].isna() & dfm["cfg_path"].isin(matched_cfg)
        dfm = dfm.drop(dfm.index[phantom])
    return dfm


def _raise_for_ambiguous_cfg_folders(dfm: pd.DataFrame) -> None:
    """Abort when one (image, series) maps to more than one config folder.

    Once cfg_folder names have been matched into the summary, the same
    (image, series) must map to a single config folder. Two different folders
    claiming the same image+series is an ambiguity that must abort the flow,
    not a shared-folder coincidence.
    """
    if "cfg_folder" in dfm.columns:
        ambiguous = (
            dfm[dfm["cfg_folder"].notna() & (dfm["cfg_folder"] != "")]
            .groupby(["image_path", "image_series_id"])["cfg_folder"]
            .nunique()
        )
        ambiguous = ambiguous[ambiguous > 1]
        if not ambiguous.empty:
            raise DuplicateEntryError(
                "image series mapped to more than one configuration folder:\n"
                f"{ambiguous.to_string()}"
            )


def _fill_cfg_only_rows(dfm: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series, pd.Series]:
    """Fill minimal entries for config rows with no scanned media.

    Config files whose referenced image was not found in the scanned media
    still belong in the summary so every config folder is visible. These rows
    get a minimal entry: folder/filename from the image reference and sheet
    routing that follows the config content (movie → Files-Timeseries,
    panel-only → Files-Stills). frames is left untouched (NaN) because the
    media-less rows have no frame count to report.

    Returns the updated frame plus the to_timeseries/to_stills masks: rows are
    routed to sheets after the column selection in the caller, so the masks
    must be recorded now, keyed by position, since the routing columns
    (has_movie, image_path) do not survive that selection.
    """
    has_movie = dfm["has_movie"].fillna(True).astype(bool) if "has_movie" in dfm.columns else pd.Series(True, index=dfm.index)
    cfg_only = dfm["cfg_path"].notna() & (dfm["cfg_path"] != "") & dfm["folder"].isna()
    if cfg_only.any():
        img_paths = dfm.loc[cfg_only, "image_path"].apply(Path)
        dfm.loc[cfg_only, "folder"] = img_paths.apply(lambda p: p.parent.as_posix())
        dfm.loc[cfg_only, "filename"] = img_paths.apply(lambda p: p.name)

    # read_summary_list() fills blanks with '' so frames may hold strings;
    # coerce to numeric so the sheet-routing comparisons work either way.
    frames_n = pd.to_numeric(dfm["frames"], errors="coerce")
    to_timeseries = (frames_n.fillna(0) > 1) | (cfg_only & has_movie)
    to_stills = ((frames_n == 1) & ~cfg_only) | (cfg_only & ~has_movie)
    return dfm, to_timeseries, to_stills


def update_from_cfg_folder(
        path_summary: Path,
        path_cfg: Path,
        relative_to: Path = None,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
):
    """
    Update the columns cfg_path and cfg_folder of microscopy movie descriptions from the folder where the cfg files are.

    When relative_to is provided, only matched image paths are rewritten relative to
    that base; unmatched rows keep their existing values untouched.

    """
    if not path_summary.exists():
        raise ValueError("Path path_summary does not exist.")
    if not path_cfg.exists():
        raise ValueError("Path path_cfg does not exist.")

    if progress_callback is not None:
        progress_callback(0, 0, "Scanning configuration files...")
    dfc = build_config_list(path_cfg, relative_to=relative_to, progress_callback=progress_callback)
    if len(dfc) == 0:
        log.info(f"No configuration files in folder {path_cfg}.")
        return

    dfs, dfsc = read_summary_list(path_summary)

    # build_config_list() emits the column as "image_series"; rename it before
    # any other use so both sides of the merge share the name "image_series_id"
    dfc.rename(columns={"image_series": "image_series_id"}, inplace=True)

    # normalize the series id on both sides: summaries may lack the column
    # entirely or hold blanks (fillna('') in read_summary_list) when the
    # reader did not report one; config files default to 0 when their DATA
    # section has no "series" key, so 0 is used as fallback
    for _df in (dfc, dfs):
        if "image_series_id" not in _df.columns:
            _df["image_series_id"] = 0
        _df["image_series_id"] = pd.to_numeric(_df["image_series_id"], errors="coerce").fillna(0).astype(int)

    dfc["img_ser"] = dfc["image_path"] + "|" + dfc["image_series_id"].astype(str)

    # pre-match duplicate guards on the (image, series) merge key: a duplicate on
    # either side would silently explode the outer merge below, producing
    # ambiguous folder mappings. Both sides must be checked: duplicate config
    # entries (two files claiming the same image+series) AND duplicate summary
    # rows. cfg_folder is intentionally not checked here — it is populated only
    # once config folders have been matched in (see the post-merge check below).
    check_duplicates(dfc, "img_ser", path_summary)

    # resolve the summary image path the same way the config side was resolved,
    # so relative folders/filenames and absolute ones compare in one frame
    def _summary_image_path(r) -> str:
        folder = Path(r["folder"])
        if not folder.is_absolute() and relative_to is not None:
            folder = Path(relative_to) / folder
        return (folder / r["filename"]).as_posix()

    dfs["image_path"] = dfs.apply(_summary_image_path, axis=1)
    dsdf = dfs.assign(img_ser=dfs["image_path"] + "|" + dfs["image_series_id"].astype(str))
    check_duplicates(dsdf, "img_ser", path_summary)

    if progress_callback is not None:
        progress_callback(0, 0, "Updating summary with configuration folders...")

    # read_summary_list() fills blanks with ''; empty strings are not null, so
    # they would win in merge_column() over the config-side values. Turn them
    # into NaN so blanks get filled from the configuration files while any
    # user edits in the summary spreadsheet are preserved.
    for col in ["cfg_path", "cfg_folder"]:
        if col in dfs:
            dfs[col] = dfs[col].replace("", np.nan)

    dfm = dfc.merge(dfs, how="right", on=["image_path", "image_series_id"])
    cfg_path_match = dfm["cfg_path_x"].notna() & ~dfm["cfg_path_x"].astype(str).str.strip().isin(["", "-"])

    for col in ["cfg_path", "cfg_folder"]:
        dfm = merge_column(dfm, col, use="y")

    dfm = _match_relative_cfg_by_suffix(dfc, dfm)
    dfm = _drop_phantom_cfg_rows(dfm)
    _raise_for_ambiguous_cfg_folders(dfm)

    dfm, to_timeseries, to_stills = _fill_cfg_only_rows(dfm)

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

        dfm[to_timeseries.to_numpy()].to_excel(writer, sheet_name="Files-Timeseries", index=False)
        dfm[to_stills.to_numpy()].to_excel(writer, sheet_name="Files-Stills", index=False)


@app.command("update-from-cfg-folder")
def update_from_cfg_folder_cli(
        path_summary: Annotated[Path, typer.Argument(help="Path of summary list in Excel or OpenOffice's fods format")],
        path_cfg: Annotated[Path, typer.Argument(help="Path where configuration files are in")],
        relative_to: Annotated[Path, typer.Option(help="Set to base where all relative image paths should be resolved to.")] = None,
):
    """
    Update the columns cfg_path and cfg_folder of microscopy movie descriptions from the folder where the cfg files are.
    """
    update_from_cfg_folder(path_summary, path_cfg, relative_to=relative_to)


def read_cfg_associations(summary_path: Path) -> pd.DataFrame | None:
    """Extract the cfg_path/cfg_folder associations stored in an existing
    summary spreadsheet.

    Rows are keyed by folder/filename (plus image_series_id when available) so
    the associations can be restored into a freshly generated summary. Returns
    None when the summary does not exist or carries no config associations.
    """
    xlsx = summary_path if summary_path.suffix == ".xlsx" else Path(f"{summary_path}.xlsx")
    if not xlsx.exists():
        return None

    try:
        df, _ = read_summary_list(xlsx)
    except (KeyError, ValueError):
        return None

    if not {"folder", "filename", "cfg_path", "cfg_folder"}.issubset(df.columns):
        return None

    assoc = df[["folder", "filename", "cfg_path", "cfg_folder"]].copy()
    if "image_series_id" in df.columns:
        assoc["image_series_id"] = pd.to_numeric(df["image_series_id"], errors="coerce").fillna(0).astype(int)

    assoc = assoc.dropna(subset=["cfg_path"])
    assoc = assoc[assoc["cfg_path"] != ""]
    return assoc if not assoc.empty else None


def restore_cfg_associations(
        summary_path: Path,
        assoc: pd.DataFrame,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
) -> None:
    """Restore cfg_path/cfg_folder associations into a summary spreadsheet.

    Associations are matched by folder/filename (plus image_series_id when
    available) and applied only to rows whose config columns are still empty,
    preserving any config paths written by more recent steps.
    """
    if assoc is None or assoc.empty:
        return

    xlsx = summary_path if summary_path.suffix == ".xlsx" else Path(f"{summary_path}.xlsx")
    if not xlsx.exists():
        return

    df, _ = read_summary_list(xlsx)
    if not {"folder", "filename", "cfg_path", "cfg_folder"}.issubset(df.columns):
        return

    keys = ["folder", "filename"]
    if "image_series_id" in df.columns and "image_series_id" in assoc.columns:
        df["image_series_id"] = pd.to_numeric(df["image_series_id"], errors="coerce").fillna(0).astype(int)
        keys = ["folder", "filename", "image_series_id"]

    dfm = df.merge(assoc, how="left", on=keys, suffixes=("", "_prev"), indicator=True)

    for col, prev_col in [("cfg_path", "cfg_path_prev"), ("cfg_folder", "cfg_folder_prev")]:
        if prev_col not in dfm.columns:
            continue
        has_prev = dfm[prev_col].notna() & (dfm[prev_col] != "")
        needs_fill = (dfm[col].isna()) | (dfm[col] == "")
        dfm[col] = dfm[col].where(~(has_prev & needs_fill), dfm[prev_col])

    dfm = dfm.drop(columns=["_merge", "cfg_path_prev", "cfg_folder_prev"], errors="ignore")

    if progress_callback is not None:
        progress_callback(0, 0, "Restoring saved config folder associations...")

    # save timeseries and stills data to excel file
    with pd.ExcelWriter(xlsx, engine="openpyxl", mode='a', engine_kwargs={'keep_vba': True}) as writer:
        wb = writer.book
        for sheet in ["Files-Timeseries", "Files-Stills"]:
            try:
                wb.remove(wb[sheet])
            except KeyError:
                pass

        dfm.query("frames > 1").to_excel(writer, sheet_name="Files-Timeseries", index=False)
        dfm.query("frames == 1").to_excel(writer, sheet_name="Files-Stills", index=False)


def make_summary_and_sync(
        path: Path,
        path_csv: Path,
        cfg_folder: Path = None,
        relative_to: Path = None,
        guess_date: bool = False,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
) -> Path:
    """Generate a summary spreadsheet and synchronise it with config files.

    Combined summary-generation flow: associations are captured from any
    pre-existing summary, a fresh summary is generated with make(), and when
    a config folder is provided the new summary is updated from the config
    files that already exist there. The captured associations are restored
    afterwards for rows that are still empty.

    Returns the path of the generated .xlsx summary spreadsheet.
    """
    old_cfg = read_cfg_associations(path_csv)

    make(path=path, path_csv=path_csv, relative_to=relative_to,
         guess_date=guess_date, progress_callback=progress_callback)

    out_path = path_csv
    if out_path.suffix == ".csv":
        out_path = out_path.parent / (out_path.name + '.xlsx')

    if cfg_folder is not None:
        if progress_callback is not None:
            progress_callback(0, 0, "Updating summary with config folder...")
        update_from_cfg_folder(out_path, ensure_dir(cfg_folder), relative_to=relative_to,
                               progress_callback=progress_callback)

    if old_cfg is not None:
        if progress_callback is not None:
            progress_callback(0, 0, "Restoring config folder associations...")
        restore_cfg_associations(out_path, old_cfg, progress_callback=progress_callback)

    return out_path


@app.command("make-and-sync")
def make_summary_and_sync_cli(
        path: Annotated[Path, typer.Argument(help="Path from where to start the search")],
        path_csv: Annotated[Path, typer.Argument(help="Output path of the list")],
        cfg_folder: Annotated[Path, typer.Option(help="Path of the configuration folder to sync the summary with")] = None,
        relative_to: Annotated[Path, typer.Option(help="Set to base where all paths should be relative to.")] = None,
        guess_date: Annotated[bool, typer.Option(help="Whether the script should extract the date from the file path.")] = False,
):
    """
    Generate a summary spreadsheet and synchronise it with existing configuration files.
    """
    make_summary_and_sync(path, path_csv, cfg_folder=cfg_folder,
                          relative_to=relative_to, guess_date=guess_date)


if __name__ == "__main__":
    app()
