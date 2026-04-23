from pathlib import Path

import pandas as pd
from pylatex import LongTable, MultiColumn
from pylatex.utils import escape_latex, NoEscape


def hyperlink(url, text):
    text = escape_latex(text)
    return NoEscape(r'\href{' + url + '}{' + text + '}')


def create_latex_table(fpath: Path, df: pd.DataFrame):
    print(fpath)

    # Generate data table
    data_table = LongTable("p{2cm} p{7cm} p{5cm}")

    data_table.add_hline()
    data_table.add_row(["experiment", "description", "file"])
    data_table.add_hline()
    data_table.end_table_header()
    data_table.add_hline()
    data_table.add_row((MultiColumn(3, align="r", data="Continued on Next Page"),))
    data_table.add_hline()
    data_table.end_table_footer()
    data_table.add_hline()
    data_table.add_row(
        (MultiColumn(3, align="r", data="End of table"),)
    )
    data_table.add_hline()
    data_table.end_table_last_footer()

    for ix, row in df.iterrows():
        opath = Path(row["output_path"])
        data_table.add_row([
            row["cfg_folder"],
            row["description"],
            hyperlink("file:" + opath.as_posix(), opath.name)
            # NoEscape(r'\url{file://' + opath.as_posix() + '}')
        ])

    data_table.generate_tex(fpath.as_posix())
