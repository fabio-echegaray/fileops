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
        ch = pd.read_excel(path, sheet_name="Channels").fillna('')
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
