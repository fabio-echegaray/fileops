import os
import re
import traceback
from pathlib import Path

import javabridge
import numpy as np
import pandas as pd
import typer
from typer import Typer
from typing_extensions import Annotated

from fileops.image import MicroManagerFolderSeries
from fileops.image.factory import load_image_file
from fileops.logger import get_logger, silence_loggers

log = get_logger(name='summary')
app = Typer()


def _guess_date(df: pd.DataFrame) -> pd.DataFrame:
    rgx = re.compile(r"[0-9]{8}") # ISO 8601

    def _d(r):
        s = str(r)
        m = re.search(rgx, s)
        if m:
            return s[m.start(): m.end()]

    df["date"] = df["folder"].apply(_d)
    # shift column 'date' to first position
    first_column = df.pop('date')
    df.insert(0, 'date', first_column)

    return df


@app.command()
def make(
        path: Annotated[Path, typer.Argument(help="Path from where to start the search")],
        path_out: Annotated[Path, typer.Argument(help="Output path of the list")],
        guess_date: Annotated[
            bool, typer.Argument(
                help="Whether the script should extract the date from the file path. "
                     "It will try to extract the date if it is in ISO 8601 format.")] = False,
):
    """
    Generate a summary list of microscope images stored in the specified path (recursively).
    The output is a file in comma separated values (CSV) format called summary.csv.
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
                if joinf not in files_visited:
                    log.info(f'Processing {joinf.as_posix()}')
                    img_struc = load_image_file(joinf)
                    if img_struc is None:
                        continue
                    out = out.append(img_struc.info, ignore_index=True)
                    files_visited.extend([Path(root) / f for f in img_struc.files])
                    r += 1
                    if type(img_struc) == MicroManagerFolderSeries:  # all files in the folder are of the same series
                        break
            except FileNotFoundError as e:
                log.error(e)
                log.warning(f'Data not found in folder {root}.')
            except (IndexError, KeyError) as e:
                log.error(e)
                log.warning(f'Data index/key not found in file; perhaps the file is truncated? (in file {joinf}).')
            except AssertionError as e:
                log.error(f'Error trying to render images from folder {root}.')
                log.error(e)
            except BaseException as e:
                log.error(e)
                log.error(traceback.format_exc())
                raise e
    if guess_date:
        out = _guess_date(out)
    out.to_csv(path_out, index=False)


def merge_column(df_merge: pd.DataFrame, column: str, use="x") -> pd.DataFrame:
    use_c = "y" if use == "x" else "x"
    df_merge[f"{column}_{use}"] = np.where(df_merge[f"{column}_{use_c}"].notnull(), df_merge[f"{column}_{use_c}"],
                                           df_merge[f"{column}_{use}"])
    df_merge = df_merge.rename(columns={f"{column}_x": f"{column}"}).drop(columns=f"{column}_y")
    return df_merge


@app.command()
def merge(
        path_a: Annotated[Path, typer.Argument(help="Path of original list")],
        path_b: Annotated[Path, typer.Argument(help="Path of list in CVS format with additional elements to be added")],
        path_out: Annotated[Path, typer.Argument(help="Output path of the list")],
):
    """
    Merge two lists of microscopy movie descriptions updating with the data of the second list.

    """

    dfa = pd.read_excel(path_a)
    dfb = pd.read_csv(path_b, index_col=False)

    merge_cols = ["folder", "filename", "image_id", "image_name"]
    df = dfa.merge(dfb, how="right", on=merge_cols)
    for col in set(dfa.columns) - set(merge_cols):
        if col in dfa and col in dfb:
            df = merge_column(df, col, use="x")

    df.to_csv(path_out, index=False)

    javabridge.kill_vm()
