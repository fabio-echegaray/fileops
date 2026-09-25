import os
import subprocess
from pathlib import Path
from typing import Callable, Optional

import numpy as np
import typer
from typing_extensions import Annotated

from fileops.export.config import _read_cfg_file, build_config_list
from fileops.logger import get_logger
from fileops.scripts._config_duplicates import check_duplicates, DuplicateEntryError
from fileops.scripts._utils import read_summary_list, path_relative
from fileops.scripts.summary import merge_column

log = get_logger(name='config_update')


def rename_movie_filename(cfg_path: Path, old_fold: str, new_fold: str):
    """Rename the ``filename`` field of the MOVIE section(s) of a config file.

    The rendered movie files themselves are left untouched: only the config
    field that names them follows the renamed configuration folder. If the old
    folder name does not appear inside a MOVIE filename the field is left as
    it is (there is nothing to replace).
    """
    lines = cfg_path.read_text().splitlines(keepends=True)
    in_movie = False
    changed = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            in_movie = stripped[1:-1].strip().upper()[:5] == "MOVIE"
            continue
        if in_movie and "=" in line:
            key, _, value = line.partition("=")
            if key.strip() == "filename" and old_fold in value:
                lines[i] = line.replace(old_fold, new_fold)
                changed = True
    if changed:
        cfg_path.write_text("".join(lines))


def update(
        lst_path: Annotated[Path, typer.Argument(help="Path where the spreadsheet file is")],
        ini_path: Annotated[Path, typer.Argument(help="Path where config files are")],
        relative_to: Annotated[Path, typer.Option(help="Set to base where all paths should be relative to.")] = None,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
):
    """
    Update config files summary list and location based on the input spreadsheet file
    """
    if not lst_path.exists():
        raise ValueError("Path lst_path does not exist.")
    if not ini_path.exists():
        raise ValueError("Path ini_path does not exist.")
    rename_folder = True
    df_cfg = build_config_list(ini_path, relative_to=relative_to)
    cfg_paths_in = "cfg_path" in df_cfg.columns and "cfg_folder" in df_cfg.columns
    df_cfg["img_ser"] = df_cfg["image_path"] + "|" + df_cfg["image_series"].astype(str)
    check_duplicates(df_cfg, "img_ser", lst_path)

    odf, chf = read_summary_list(lst_path)
    odf["path"] = odf.apply(lambda r: (Path(r["folder"]) / r["filename"]).as_posix()
                                      + "|" + str(r["image_series_id"] if "image_series_id" in r else 0), axis=1)
    try:
        check_duplicates(odf, "path", lst_path)
    except DuplicateEntryError as e:
        log.warning(f"Duplicated entries in the path column were found in table {lst_path.absolute()}.\n"
                    "Sometimes this happens when the file format can store several image series in one file.\n"
                    "Check if this is the case.")
    try:
        check_duplicates(odf, "cfg_folder", lst_path)
    except DuplicateEntryError as e:
        log.warning(f"Duplicated entries in the cfg_folder column were found in table {lst_path.absolute()}.\n"
                    "This happens when several image series share a configuration folder, each with its own\n"
                    "config file, and is not an error.")
    # assert len(odf["path"]) - len(odf["path"].drop_duplicates()) == 0, "path duplicates found in the input spreadsheet"
    # assert len(df["image"]) - len(df["image"].drop_duplicates()) == 0, "path duplicates found in the input spreadsheet"

    df_cfg = df_cfg[["cfg_path", "cfg_folder", "img_ser"]].merge(odf, how="right", left_on="img_ser", right_on="path")
    df_cfg = merge_column(df_cfg, "cfg_folder", use="y")

    def __new_path(row):
        if (
                (type(row["cfg_path_x"]) == float and np.isnan(row["cfg_path_x"]))
                or row["cfg_path_x"] == "-" or len(row["cfg_path_x"]) == 0
                or not isinstance(row["cfg_folder"], str)
                or row["cfg_folder"] in ("", "-")):
            return
        oldpath = Path(row["cfg_path_x"])
        # keep the folder structure above the cfg folder intact, only the
        # leaf folder name (the cfg_folder) may change.
        out_path = oldpath.parent.parent / row["cfg_folder"] / oldpath.name

        return out_path

    df_cfg["old_path"] = df_cfg["cfg_path_x"]
    df_cfg["new_path"] = df_cfg.apply(__new_path, axis=1)
    ren_df = df_cfg[["ix", "old_path", "new_path"]].copy()

    # drop rows that don't need update
    drop_ix = ren_df["old_path"] == ren_df["new_path"]
    ren_df = ren_df[~drop_ix]
    ren_df.dropna(subset=["old_path", "new_path"], inplace=True)

    # remove irrelevant columns and merge the remaining
    df_cfg.drop(columns=["img_ser", "path", "old_path", "new_path"], inplace=True)
    if cfg_paths_in:
        for col in ["cfg_path", "cfg_folder"]:
            df_cfg = merge_column(df_cfg, col, use="x")
    if relative_to is not None:
        df_cfg = path_relative(df_cfg, relative_to, path_columns=["folder"])

    # make columns of current config path and build the new path where it should go
    # if original path does not exist, skip row
    if rename_folder:
        print("renaming folders...")
        to_rename = ren_df.dropna(subset=["old_path", "new_path"])
        total = len(to_rename)
        if progress_callback is not None:
            progress_callback(0, total, "Renaming configuration folders...")
        for n, (ix, row) in enumerate(to_rename.iterrows(), start=1):
            old_path = Path(row["old_path"])
            new_path = Path(row["new_path"])
            if not old_path.is_absolute():
                old_path = (ini_path / old_path).resolve()
            if not new_path.is_absolute():
                new_path = (ini_path / new_path).resolve()
            if not old_path.exists():
                continue
            if old_path != new_path:
                try:
                    # guard: only rename files that still parse as a config so a
                    # corrupt/broken entry is skipped. Parse only: it must not
                    # require loading the image (which is resolved via a root
                    # path) for a rename that does not touch the image.
                    cfg = _read_cfg_file(old_path)
                    if "DATA" not in cfg.sections():
                        continue
                    new_path.parent.mkdir(parents=True, exist_ok=True)
                    if progress_callback is not None:
                        progress_callback(n, total, f"Renaming {old_path.name}...")
                    log.info(f"renaming {old_path} to {new_path}")
                    o = subprocess.run(["git", "mv", old_path.as_posix(), new_path.as_posix()], capture_output=True)

                    if b'fatal' in o.stderr:  # file not in git system
                        # try plain OS move
                        os.rename(old_path, new_path)

                    old_fold = old_path.parent.name
                    new_fold = new_path.parent.name
                    if old_fold != new_fold:
                        rename_movie_filename(new_path, old_fold, new_fold)
                except Exception as e:
                    log.warning(e)
                    continue

        ren_map = ren_df.set_index("ix")["new_path"]
        df_cfg["cfg_path"] = df_cfg["ix"].map(ren_map).fillna(df_cfg["cfg_path"])

    df_cfg.to_excel(lst_path.parent / "cfg_merge.xlsx", index=False)


def update_cli(
        lst_path: Annotated[Path, typer.Argument(help="Path where the spreadsheet file is")],
        ini_path: Annotated[Path, typer.Argument(help="Path where config files are")],
        relative_to: Annotated[Path, typer.Option(help="Set to base where all paths should be relative to.")] = None,
):
    """
    Update config files summary list and location based on the input spreadsheet file
    """
    update(lst_path, ini_path, relative_to=relative_to)
