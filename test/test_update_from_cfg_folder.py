import tempfile
import unittest
from pathlib import Path

import pandas as pd

from fileops.scripts.summary import update_from_cfg_folder


def _cfg_file_text(image_path: Path, series: int = None) -> str:
    text = f"[DATA]\nimage = {image_path.as_posix()}\n"
    if series is not None:
        text += f"series = {series}\n"
    text += (
        "\n[MOVIE-1]\n"
        "title = Test movie\n"
        "description = test\n"
        "filename = movie\n"
        "fps = 10\n"
        "layout = twoch\n"
    )
    return text


class TestUpdateFromCfgFolder(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.img_dir = self.tmp / "images"
        self.img_dir.mkdir(parents=True)
        self.cfg_dir = self.tmp / "cfg" / "exp1"
        self.cfg_dir.mkdir(parents=True)
        self.summary_path = self.tmp / "summary.xlsx"

    def tearDown(self):
        self._tmp.cleanup()

    def _write_summary(self, rows):
        df = pd.DataFrame(rows)
        with pd.ExcelWriter(self.summary_path, engine="openpyxl") as writer:
            pd.DataFrame(columns=["name"]).to_excel(writer, sheet_name="Channels", index=False)
            df.to_excel(writer, sheet_name="Files-Timeseries", index=False)

    def _read_timeseries(self) -> pd.DataFrame:
        return pd.read_excel(self.summary_path, sheet_name="Files-Timeseries")

    def _run_update(self, series=None) -> Path:
        image_path = self.img_dir / "movie.nd2"
        cfg_path = self.cfg_dir / "movie.cfg"
        cfg_path.write_text(_cfg_file_text(image_path, series=series))
        update_from_cfg_folder(self.summary_path, self.cfg_dir.parent)
        return cfg_path

    def test_blank_image_series_id_is_matched_and_updated(self):
        # rows whose reader did not report a series id (e.g. Nikon files) end up
        # blank ('' after fillna) in the spreadsheet; they must still match a
        # configuration whose DATA section has no "series" key (default 0)
        self._write_summary({
            "ix":              [0],
            "folder":          [self.img_dir.as_posix()],
            "filename":        ["movie.nd2"],
            "frames":          [10],
            "cfg_path":        [""],
            "cfg_folder":      [""],
            "image_series_id": [None],
        })
        cfg_path = self._run_update()

        out = self._read_timeseries()
        self.assertEqual(len(out), 1)
        self.assertEqual(out.loc[0, "cfg_path"], cfg_path.as_posix())
        self.assertEqual(out.loc[0, "cfg_folder"], self.cfg_dir.name)
        self.assertEqual(int(out.loc[0, "image_series_id"]), 0)

    def test_missing_image_series_id_column_is_tolerated(self):
        # summaries generated before image_series_id existed lack the column
        self._write_summary({
            "ix":         [0],
            "folder":     [self.img_dir.as_posix()],
            "filename":   ["movie.nd2"],
            "frames":     [10],
            "cfg_path":   [""],
            "cfg_folder": [""],
        })
        cfg_path = self._run_update()

        out = self._read_timeseries()
        self.assertEqual(len(out), 1)
        self.assertEqual(out.loc[0, "cfg_path"], cfg_path.as_posix())

    def test_explicit_series_id_is_preserved(self):
        # rows with a real id must keep matching on (image_path, id)
        self._write_summary({
            "ix":              [0],
            "folder":          [self.img_dir.as_posix()],
            "filename":        ["movie.nd2"],
            "frames":          [10],
            "cfg_path":        [""],
            "cfg_folder":      [""],
            "image_series_id": [3],
        })
        cfg_path = self._run_update(series=3)

        out = self._read_timeseries()
        self.assertEqual(len(out), 1)
        self.assertEqual(out.loc[0, "cfg_path"], cfg_path.as_posix())
        self.assertEqual(int(out.loc[0, "image_series_id"]), 3)

    def test_user_edits_are_preserved_but_blanks_get_filled(self):
        # merge_column(use="y") prefers the summary side: a genuine edit must
        # survive, while blanks (not valid values) must be filled from the
        # configuration files
        self._write_summary({
            "ix":              [0],
            "folder":          [self.img_dir.as_posix()],
            "filename":        ["movie.nd2"],
            "frames":          [10],
            "cfg_path":        ["user/edited/movie.cfg"],
            "cfg_folder":      ["user_edit"],
            "image_series_id": [None],
        })
        self._run_update()

        out = self._read_timeseries()
        self.assertEqual(out.loc[0, "cfg_path"], "user/edited/movie.cfg")
        self.assertEqual(out.loc[0, "cfg_folder"], "user_edit")


if __name__ == '__main__':
    unittest.main()
