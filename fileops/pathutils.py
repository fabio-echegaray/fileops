import fnmatch
import os
import re
from pathlib import Path, PurePath
from typing import Union, List

import pandas as pd

_iso8601_rgx = re.compile(r"[0-9]{8}")  # ISO 8601


def relpath_from_date(s: str) -> str:
    p = Path(s)
    visited_lst = list()
    current_p = p
    while True:
        visited_lst.append(current_p.name)
        m = re.search(_iso8601_rgx, current_p.name)
        if m:
            return str(Path(*reversed(visited_lst)))
        else:
            current_p = current_p.parent


def guess_date_in_path(df: pd.DataFrame, date_col_name="folder") -> pd.DataFrame:
    def _d(r):
        s = str(r)
        m = re.search(_iso8601_rgx, s)
        if m:
            return s[m.start(): m.end()]
        return None

    df["date"] = df[date_col_name].apply(_d)
    # shift column 'date' to first position
    first_column = df.pop("date")
    df.insert(0, "date", first_column)

    return df


def ensure_dir(dir_path: Union[str, Path]):
    is_path = isinstance(dir_path, PurePath)
    adir_path = os.path.abspath(dir_path)
    if not os.path.exists(adir_path):
        os.makedirs(adir_path, exist_ok=True)
    return Path(dir_path) if is_path else dir_path


def find(pattern, path) -> List[Path]:
    result = []
    for root, dirs, files in os.walk(path):
        for name in files:
            if fnmatch.fnmatch(name, pattern):
                result.append(Path(root) / name)
    return result
