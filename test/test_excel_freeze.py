import tempfile
import unittest
from pathlib import Path

import openpyxl
import pandas as pd

from fileops.scripts._config_edit import generate_config_content
from fileops.scripts._config_map import write_config_map
from fileops.scripts.summary import merge


def _freeze_panes(path, sheet):
    book = openpyxl.load_workbook(path)
    try:
        return book[sheet].freeze_panes
    finally:
        book.close()


class TestExcelFreezePanes(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_write_config_map_freezes_configs_header(self):
        path = self.tmp / "cfg_content.xlsx"
        write_config_map(path, pd.DataFrame([{
            "cfg_folder": "exp1", "cfg_path": "", "image_path": "a.nd2",
            "image_series_id": 0,
        }]))

        self.assertEqual(_freeze_panes(path, "Configs"), "A2")

    def test_generate_config_content_freezes_both_sheets(self):
        cfg_root = self.tmp / "export"
        cfg_dir = cfg_root / "exp1"
        cfg_dir.mkdir(parents=True)
        img = cfg_root / "img.nd2"
        img.write_bytes(b"fake")
        (cfg_dir / "export_definition.cfg").write_text(
            f"[DATA]\nimage = {img.as_posix()}\n\n"
            "[MOVIE-1]\ntitle = t\ndescription = d\nfilename = m\n")

        out = self.tmp / "cfg_content.xlsx"
        generate_config_content(cfg_root, out, with_latex_table=False)

        self.assertEqual(_freeze_panes(out, "Content"), "A2")
        self.assertEqual(_freeze_panes(out, "Configs"), "A2")

    def test_summary_merge_freezes_files_timeseries_header(self):
        def _write(path, ix):
            with pd.ExcelWriter(path, engine="openpyxl") as writer:
                pd.DataFrame({
                    "ix":         [ix],
                    "folder":     ["/data/20230726/exp1"],
                    "filename":   ["a.nd2"],
                    "image_name": ["img"],
                }).to_excel(writer, sheet_name="Files-Timeseries", index=False)

        a = self.tmp / "a.xlsx"
        b = self.tmp / "b.xlsx"
        out = self.tmp / "out.xlsx"
        _write(a, 0)
        _write(b, 0)

        merge(a, b, out)

        self.assertEqual(_freeze_panes(out, "Files-Timeseries"), "A2")


if __name__ == '__main__':
    unittest.main()
