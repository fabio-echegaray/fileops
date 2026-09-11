import tempfile
import unittest
from pathlib import Path

import pandas as pd

from fileops.scripts.summary import read_cfg_associations, restore_cfg_associations


class TestCfgAssociations(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.summary_path = self.tmp / "summary.csv.xlsx"

    def tearDown(self):
        self._tmp.cleanup()

    def _write_summary(self, rows, as_assoc=False):
        df = pd.DataFrame(rows)
        with pd.ExcelWriter(self.summary_path, engine="openpyxl") as writer:
            pd.DataFrame(columns=["name"]).to_excel(writer, sheet_name="Channels", index=False)
            df.to_excel(writer, sheet_name="Files-Timeseries", index=False)
        return df

    def _read_timeseries(self):
        return pd.read_excel(self.summary_path, sheet_name="Files-Timeseries")

    def test_read_returns_none_when_summary_missing(self):
        self.assertIsNone(read_cfg_associations(self.tmp / "does-not-exist.csv"))

    def test_read_returns_none_when_no_associations(self):
        self._write_summary({
            "folder":     ["data/a"],
            "filename":   ["a.nd2"],
            "frames":     [10],
            "cfg_path":   [""],
            "cfg_folder": [""],
        })
        self.assertIsNone(read_cfg_associations(self.summary_path))

    def test_read_extracts_cfg_associations(self):
        self._write_summary({
            "folder":          ["data/a", "data/b"],
            "filename":        ["a.nd2", "b.nd2"],
            "frames":          [10, 1],
            "cfg_path":        ["cfg/exp1/export_definition.cfg", ""],
            "cfg_folder":      ["exp1", ""],
            "image_series_id": [1, 2],
        })
        assoc = read_cfg_associations(self.summary_path)
        self.assertEqual(len(assoc), 1)
        self.assertEqual(assoc.loc[0, "filename"], "a.nd2")
        self.assertEqual(assoc.loc[0, "cfg_path"], "cfg/exp1/export_definition.cfg")
        self.assertEqual(int(assoc.loc[0, "image_series_id"]), 1)

    def test_restore_fills_empty_cells_only(self):
        self._write_summary({
            "folder":          ["data/a"],
            "filename":        ["a.nd2"],
            "frames":          [10],
            "cfg_path":        ["cfg/exp1/export_definition.cfg"],
            "cfg_folder":      ["exp1"],
            "image_series_id": [1],
        })
        assoc = read_cfg_associations(self.summary_path)
        self.assertIsNotNone(assoc)

        # a freshly generated summary drops config columns; restore must re-add
        self._write_summary({
            "folder":          ["data/a"],
            "filename":        ["a.nd2"],
            "frames":          [10],
            "cfg_path":        [""],
            "cfg_folder":      [""],
            "image_series_id": [1],
        })
        restore_cfg_associations(self.summary_path, assoc)

        out = self._read_timeseries()
        self.assertEqual(out.loc[0, "cfg_path"], "cfg/exp1/export_definition.cfg")
        self.assertEqual(out.loc[0, "cfg_folder"], "exp1")

    def test_restore_keeps_more_recent_values(self):
        assoc = pd.DataFrame({
            "folder":          ["data/a"],
            "filename":        ["a.nd2"],
            "cfg_path":        ["old/cfg.cfg"],
            "cfg_folder":      ["old"],
            "image_series_id": [1],
        })
        # row no longer matches (folder changed); nothing should be restored
        self._write_summary({
            "folder":          ["data/changed"],
            "filename":        ["a.nd2"],
            "frames":          [10],
            "cfg_path":        [""],
            "cfg_folder":      [""],
            "image_series_id": [1],
        })
        restore_cfg_associations(self.summary_path, assoc)

        out = self._read_timeseries()
        self.assertTrue(pd.isna(out.loc[0, "cfg_path"]) or out.loc[0, "cfg_path"] == "")


if __name__ == '__main__':
    unittest.main()