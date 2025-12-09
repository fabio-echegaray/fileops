from pathlib import Path

import numpy as np
import pandas as pd
from pandas_ods_reader import read_ods


def _read_summary_list(path: Path) -> pd.DataFrame:
    df = pd.DataFrame()
    if np.any([e in path.suffixes for e in ('.xls', '.xlsx')]):
        df = pd.read_excel(path).fillna('')
    elif np.any([e in path.suffixes for e in ('.ods', '.fods',)]):
        df = read_ods(path)
    return df
