import os
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

from fileops.export.config import build_config_list, read_config


def check_duplicates(df: pd.DataFrame, column: str):
    if len(df[column].dropna()) - len(df[column].dropna().drop_duplicates()) > 0:
        counts = df.groupby(column, as_index=False).size().sort_values("size", ascending=False)
        counts.to_excel(f"counts-{column}.xlsx")
        print(counts)
        raise IndexError(f"duplicates found in column {column} of the dataframe")


def merge_column(df_merge: pd.DataFrame, column: str, use="x") -> pd.DataFrame:
    use_c = "y" if use == "x" else "x"
    # df_merge[f"{column}_{use}"] = np.where(df_merge[f"{column}_{use_c}"].notnull(), df_merge[f"{column}_{use_c}"],
    #                                        df_merge[f"{column}_{use}"])
    df_merge[f"{column}_{use}"] = df_merge[f"{column}_{use_c}"]
    df_merge = df_merge.rename(columns={f"{column}_x": f"{column}"}).drop(columns=f"{column}_y")
    return df_merge


if __name__ == '__main__':
    rename_folder = False
    ini_path = Path("/media/lab/Data/Fabio/export/Nikon/")
    df_cfg = build_config_list(ini_path)
    cfg_paths_in = "cfg_path" in df_cfg.columns and "cfg_folder" in df_cfg.columns
    df_cfg.to_excel("config.xlsx", index=False)
    check_duplicates(df_cfg, "image")

    odf = pd.read_excel("summary of CPF data.xlsx")
    odf["path"] = odf.apply(lambda r: (Path(r["folder"]) / r["filename"]).as_posix(), axis=1)
    check_duplicates(odf, "path")
    check_duplicates(odf, "cfg_folder")
    # assert len(odf["path"]) - len(odf["path"].drop_duplicates()) == 0, "path duplicates found in the input spreadsheet"
    # assert len(df["image"]) - len(df["image"].drop_duplicates()) == 0, "path duplicates found in the input spreadsheet"

    df_cfg = df_cfg[["cfg_path", "cfg_folder", "image"]].merge(odf, how="right", left_on="image", right_on="path")


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

    df_cfg = df_cfg.drop(columns=["image", "path", "old_path", "new_path"])
    if cfg_paths_in:
        for col in ["cfg_path", "cfg_folder"]:
            df_cfg = merge_column(df_cfg, col, use="x")

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

                # check if there is a rendered movie and change name accordingly
                fname = cfg.movie_filename
                old_fld_name = Path(row["old_path"]).parent.name
                old_mv_name = old_path.parent.name + "-" + fname + ".twoch.mp4"
                new_mv_name = new_path.parent.name + "-" + fname + ".twoch.mp4"
                if old_mv_name != new_mv_name:
                    try:
                        os.rename(cfg.path.parent / old_mv_name, cfg.path.parent / new_mv_name)
                    except FileNotFoundError:
                        print(f"Skipping movie {old_mv_name}")

        df_cfg["cfg_path"] = ren_df["new_path"]
        os.chdir(cwd)

    df_cfg.to_excel("cfg_merge.xlsx", index=False)
