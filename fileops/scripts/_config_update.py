import os
import subprocess
from pathlib import Path
from typing import Callable, Optional

import numpy as np
import typer
from typing_extensions import Annotated

from fileops.export.config import build_config_list, read_config
from fileops.logger import get_logger
from fileops.scripts._config_duplicates import check_duplicates, DuplicateEntryError
from fileops.scripts._utils import _read_summary_list, path_relative
from fileops.scripts.summary import merge_column

log = get_logger(name='config_update')


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
    df_cfg = build_config_list(ini_path)
    cfg_paths_in = "cfg_path" in df_cfg.columns and "cfg_folder" in df_cfg.columns
    df_cfg["img_ser"] = df_cfg["image_path"] + "|" + df_cfg["image_series"].astype(str)
    check_duplicates(df_cfg, "img_ser", lst_path)

    odf, chf = _read_summary_list(lst_path)
    odf["path"] = odf.apply(lambda r: (Path(r["folder"]) / r["filename"]).as_posix()
                                      + "|" + str(r["image_series_id"] if "image_series_id" in r else 0), axis=1)
    try:
        check_duplicates(odf, "path", lst_path)
    except DuplicateEntryError as e:
        log.warning(f"Duplicated entries in the path column were found in table {lst_path.absolute()}.\n"
                    "Sometimes this happens when the file format can store several image series in one file.\n"
                    "Check if this is the case.")
    check_duplicates(odf, "cfg_folder", lst_path)
    # assert len(odf["path"]) - len(odf["path"].drop_duplicates()) == 0, "path duplicates found in the input spreadsheet"
    # assert len(df["image"]) - len(df["image"].drop_duplicates()) == 0, "path duplicates found in the input spreadsheet"

    df_cfg = df_cfg[["cfg_path", "cfg_folder", "img_ser"]].merge(odf, how="right", left_on="img_ser", right_on="path")

    def __new_path(row):
        if (
                (type(row["cfg_path_x"]) == float and np.isnan(row["cfg_path_x"]))
                or row["cfg_path_x"] == "-" or len(row["cfg_path_x"]) == 0
        ) \
                or (type(row["cfg_folder_y"]) == float and np.isnan(row["cfg_folder_y"])):
            return
        oldpath = Path(row["cfg_path_x"])
        out_path = oldpath.parent.parent / row["cfg_folder_y"] / oldpath.name

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
        cwd = os.getcwd()
        os.chdir(ini_path)
        for ix, row in ren_df.dropna(subset=["old_path", "new_path"]).iterrows():
            old_path = Path(row["old_path"])
            new_path = Path(row["new_path"])
            if not old_path.exists():
                continue
            if old_path != new_path:
                cfg = read_config(old_path)

                try:
                    os.mkdir(new_path.parent)
                    try:
                        if progress_callback is not None:
                            progress_callback(n, total, f"Renaming {old_path.name}...")
                        print(f"renaming {old_path} to {new_path}")
                        o = subprocess.run(["git", "mv", old_path.as_posix(), new_path.as_posix()], capture_output=True)

                        if b'fatal' in o.stderr:  # file not in git system
                            # try plain OS move
                            os.rename(old_path, new_path)
                        os.rmdir(old_path.parent)
                    except Exception as e:
                        print(e)
                        os.rmdir(new_path.parent)
                        raise
                except FileExistsError as e:
                    print(f"Skipping to move file {old_path} because new path already exists.")
                    continue

        df_cfg["cfg_path"] = ren_df["new_path"]
        os.chdir(cwd)

    df_cfg.to_excel(lst_path.parent / "cfg_merge.xlsx", index=False)
