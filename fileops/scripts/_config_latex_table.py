from pathlib import Path

import pandas as pd
from pylatex import LongTable, MultiColumn
from pylatex.utils import escape_latex, NoEscape


def hyperlink(url, text):
    text = escape_latex(text)
    return NoEscape(r'\href{' + url + '}{' + text + '}')


def create_latex_table(fpath: Path, df: pd.DataFrame, paths_relative_to: Path = None):
    print(fpath)

    # Generate data table
    data_table = LongTable("p{4cm} p{10cm}")

    data_table.add_hline()
    data_table.add_row([NoEscape("Link\\newline(experiment tag)"), "description"])
    data_table.add_hline()
    data_table.end_table_header()
    data_table.add_hline()
    data_table.add_row((MultiColumn(2, align="r", data="Continued on Next Page"),))
    data_table.add_hline()
    data_table.end_table_footer()
    data_table.add_hline()
    data_table.add_row(
        (MultiColumn(2, align="r", data="End of table"),)
    )
    data_table.add_hline()
    data_table.end_table_last_footer()

    for ix, row in df.iterrows():
        if paths_relative_to is not None:
            opath = Path(row["output_path"]).relative_to(paths_relative_to)
        else:
            opath = Path(row["output_path"])
        data_table.add_row([
            NoEscape(f"\href{{file:{opath.as_posix()} }}{{ {opath.name} }} \\newline({row['cfg_folder']})"),
            row["description"],
            # NoEscape(r'\url{file://' + opath.as_posix() + '}')
        ])

    data_table.generate_tex(fpath.as_posix())
