from pathlib import Path
from typing import Tuple, List

import numpy as np
import pandas as pd
from pandas import read_csv
from pandas_ods_reader import read_ods


def _read_summary_list(path: Path) -> Tuple[pd.DataFrame, pd.DataFrame | None]:
    df = pd.DataFrame()
    if np.any([e in path.suffixes for e in ('.xls', '.xlsx')]):
        df = pd.read_excel(path, sheet_name="Files-Timeseries").fillna('')
        try:
            ch = pd.read_excel(path, sheet_name="Channels").fillna('')
        except (KeyError, ValueError):
            ch = None
    elif np.any([e in path.suffixes for e in ('.ods', '.fods',)]):
        try:  # assume there are sheets
            df = read_ods(path, "Files-Timeseries").fillna('')
            ch = read_ods(path, "Channels").fillna('')
        except KeyError:  # there were no sheets
            df = read_ods(path, ).fillna('')
            ch = None
    elif np.any([e in path.suffixes for e in ('.csv',)]):
        df = read_csv(path)
        ch = None
    return df, ch


def _path_relative(path, relative_path) -> Path:
    try:
        path = Path(path)
        rel_path = path.relative_to(relative_path)
        return rel_path
    except ValueError:  # when relative_path is not in the subpath of path
        return path


def path_relative(df: pd.DataFrame, to: Path, path_columns=List[str]) -> pd.DataFrame:
    for c in path_columns:
        # replace the column (not df.loc[:, c] = ...) so that pandas does not try
        # to cast the Path objects back into the column's existing dtype (e.g. the
        # strict 'str' dtype under pandas 3.x), which raises
        # "TypeError: Invalid value '...' for dtype 'str'".
        df[c] = df[c].apply(_path_relative, args=(to,))

    return df
