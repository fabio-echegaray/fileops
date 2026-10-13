import tempfile
import unittest
from pathlib import Path

import pandas as pd

from fileops.scripts import read_summary_list


class TestReadSummaryList(unittest.TestCase):

    def setUp(self):
        self._tmpdir = Path(tempfile.mkdtemp())

    def _make_xlsx(self, name, with_channels=True):
        path = self._tmpdir / name
        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            pd.DataFrame({"a": [1]}).to_excel(writer, sheet_name="Files-Timeseries", index=False)
            if with_channels:
                pd.DataFrame({"name": ["ch1"]}).to_excel(writer, sheet_name="Channels", index=False)
        return path

    def test_xlsx_with_channels(self):
        path = self._make_xlsx("with_channels.xlsx", with_channels=True)
        df, ch = read_summary_list(path)
        self.assertIsNotNone(df)
        self.assertIsNotNone(ch)
        self.assertIn("name", ch.columns)

    def test_xlsx_without_channels(self):
        path = self._make_xlsx("no_channels.xlsx", with_channels=False)
        df, ch = read_summary_list(path)
        self.assertIsNotNone(df)
        self.assertIsNone(ch)

    def test_csv_is_rejected(self):
        # only the canonical xlsx format is supported; csv must not be read
        path = self._tmpdir / "data.csv"
        pd.DataFrame({"a": [1]}).to_csv(path, index=False)
        with self.assertRaises(ValueError):
            read_summary_list(path)

    def test_ods_is_rejected(self):
        path = self._tmpdir / "data.fods"
        path.write_text("irrelevant")
        with self.assertRaises(ValueError):
            read_summary_list(path)


if __name__ == '__main__':
    unittest.main()
