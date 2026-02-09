from pathlib import Path
from typing import Tuple

import numpy as np
import pandas as pd
from pandas_ods_reader import read_ods


def _read_summary_list(path: Path) -> Tuple[pd.DataFrame, pd.DataFrame | None]:
    df = pd.DataFrame()
    if np.any([e in path.suffixes for e in ('.xls', '.xlsx')]):
        df = pd.read_excel(path, sheet_name="Files-Timeseries").fillna('')
        ch = pd.read_excel(path, sheet_name="Channels").fillna('')
    elif np.any([e in path.suffixes for e in ('.ods', '.fods',)]):
        df = read_ods(path)
        ch = None
    return df, ch
