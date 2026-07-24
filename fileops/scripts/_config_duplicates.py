from pathlib import Path

import pandas as pd

from fileops.logger import get_logger

log = get_logger(name='config_dupes')


class DuplicateEntryError(Exception):
    """Raised when a dataframe contains duplicate entries in a column."""
    pass


def check_duplicates(df: pd.DataFrame, column: str, lst_path: Path = None):
    if len(df[column].dropna()) - len(df[column].dropna().drop_duplicates()) > 0:
        grp = df.groupby(column, as_index=False)
        counts = grp.size().sort_values("size", ascending=False)
        counts["cfg_folder"] = counts[column].apply(lambda r: ", ".join(df[df[column] == r]["cfg_folder"]))
        out_path = lst_path.parent / f"counts-{column}.xlsx" if lst_path else Path(f"counts-{column}.xlsx")
        counts.to_excel(out_path)
        log.info("\r\n" + str(counts))
        raise DuplicateEntryError(f"duplicates found in column {column} of the dataframe")
