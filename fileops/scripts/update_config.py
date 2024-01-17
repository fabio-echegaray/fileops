import os
import re
from pathlib import Path

import pandas as pd

from fileops.export.config import build_config_list


def reorder_name(old_df: pd.DataFrame, new_col_name="new_folder") -> pd.DataFrame:
    if new_col_name not in old_df.columns:
        old_df[new_col_name] = None

    for idx, row in old_df.iterrows():
        # main_cond, num, sub_cond = re.search(r'^([a-z]*)-([0-9]*)-*([a-z]*)$', r["cfg_folder"]).groups()
        main_cond = row["cfg_folder"].split("-")[0]
        num = row["cfg_folder"].split("-")[1]
        sub_cond = "-".join(row["cfg_folder"].split("-")[2:])
        print(f"ix={idx} num={num} main_cond={main_cond} sub_cond={sub_cond}")

        df.iloc[idx][new_col_name] = f"{num}-{main_cond}-{sub_cond}" if sub_cond else f"{num}-{main_cond}"

    return df


def merge_column(df_merge: pd.DataFrame, column: str, use="x") -> pd.DataFrame:
    use_c = "y" if use == "x" else "x"
    df_merge[f"{column}_{use}"] = np.where(df_merge[f"{column}_{use_c}"].notnull(), df_merge[f"{column}_{use_c}"],
                                           df_merge[f"{column}_{use}"])
    df_merge = df_merge.rename(columns={f"{column}_x": f"{column}"}).drop(columns=f"{column}_y")
    return df_merge


if __name__ == '__main__':
    rename_folder = False
    ini_path = Path("/media/lab/Data/Fabio/export/Nikon/")
    df = build_config_list(ini_path)
    cfg_paths_in = "cfg_path" in df.columns and "cfg_folder" in df.columns
    print(df)

    if rename_folder:
        print("renaming folders...")
        df = reorder_name(df, new_col_name="new_folder")
        cwd = os.getcwd()
        os.chdir(ini_path)
        for ix, row in df.iterrows():
            # os.rename(Path(r["cfg_path"]).parent,
            #           Path(r["cfg_path"]).parent.parent / r["new_folder"])
            old_path = re.escape(Path(row["cfg_path"]).parent.as_posix())
            new_path = re.escape((Path(row["cfg_path"]).parent.parent / row["new_folder"]).as_posix())
            os.system(f"git mv {old_path} {new_path}")

        os.chdir(cwd)
        df = df.drop(columns=["new_folder"])

    df.to_excel("config.xlsx", index=False)

    odf = pd.read_excel("summary of CPF data.xlsx")
    odf["path"] = odf.apply(lambda r: (Path(r["folder"]) / r["filename"]).as_posix(), axis=1)
    df = df.merge(odf, how="right", left_on="image", right_on="path")
    df = df.drop(columns=["image", "path"])
    if cfg_paths_in:
        for col in ["cfg_path", "cfg_folder"]:
            df = merge_column(df, col, use="x")

    df.to_excel("cfg_merge.xlsx", index=False)
