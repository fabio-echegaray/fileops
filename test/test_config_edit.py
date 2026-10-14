import configparser
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from fileops.scripts._config_edit import _select_movie_section, edit_config_content

_CFG = (
    "[DATA]\nimage = /data/img.tif\n\n"
    "[MOVIE-1]\nfilename = a.mp4\ntitle = A\ndescription = first\n\n"
    "[MOVIE-2]\nfilename = b.mp4\ntitle = B\ndescription = second\n"
)


def _row(cfg_path, movie_name, title, description):
    return {"cfg_path": str(cfg_path), "image_path": "/data/img.tif", "movie_name": movie_name,
            "title": title, "description": description, "fps": 10, "layout": "x",
            "z_projection": "max", "bitrate": "1M"}


class TestMultiMovieMapping(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.cfg = self.tmp / "m.cfg"
        self.cfg.write_text(_CFG)

    def _edit(self, rows):
        xlsx = self.tmp / "content.xlsx"
        pd.DataFrame(rows).to_excel(xlsx, sheet_name="Content", index=False)
        edit_config_content(xlsx)
        cp = configparser.ConfigParser()
        cp.read(self.cfg)
        return cp

    def test_rows_land_on_their_own_sections_with_semicolon(self):
        cp = self._edit([_row(self.cfg, "a.mp4", "TA", "1hr collection; 2hr incubation"),
                         _row(self.cfg, "b.mp4", "TB", "other")])
        self.assertEqual(cp["MOVIE-1"]["title"], "TA")
        self.assertEqual(cp["MOVIE-1"]["description"], "1hr collection; 2hr incubation")
        self.assertEqual(cp["MOVIE-2"]["title"], "TB")
        self.assertEqual(cp["MOVIE-2"]["description"], "other")

    def test_unmatched_row_does_not_fall_back_to_first_section(self):
        cp = self._edit([_row(self.cfg, "zzz.mp4", "WRONG", "WRONG")])
        self.assertEqual(cp["MOVIE-1"]["title"], "A")
        self.assertEqual(cp["MOVIE-2"]["title"], "B")

    def test_select_raises_when_ambiguous_or_missing(self):
        cp = configparser.ConfigParser()
        cp.read_string(_CFG)
        with self.assertRaises(ValueError):
            _select_movie_section(cp, "zzz.mp4")
        cp.set("MOVIE-2", "filename", "a.mp4")
        with self.assertRaises(ValueError):
            _select_movie_section(cp, "a.mp4")


class TestNonAsciiPaths(unittest.TestCase):
    def test_non_ascii_image_path_roundtrips_as_utf8(self):
        tmp = Path(tempfile.mkdtemp())
        cfg = tmp / "u.cfg"
        path = "/data/müller/näïve_日本語/img.tif"
        cfg.write_bytes(("[DATA]\nimage = %s\n\n[MOVIE]\nfilename = a.mp4\n" % path).encode("utf-8"))
        row = _row(cfg, "a.mp4", "T", "D")
        row["image_path"] = path
        xlsx = tmp / "content.xlsx"
        pd.DataFrame([row]).to_excel(xlsx, sheet_name="Content", index=False)
        edit_config_content(xlsx)
        self.assertIn(path, cfg.read_bytes().decode("utf-8"))


class TestSeriesPreserved(unittest.TestCase):
    def test_edit_keeps_own_series_and_does_not_inject_inherited_one(self):
        """#64: edit_config_content() never writes `series`; layered values read back intact."""
        from fileops.export.config import build_config_list
        tmp = Path(tempfile.mkdtemp())
        (tmp / "defaults.cfg").write_text("[DATA]\nseries = 5\n")
        img = tmp / "s" / "d" / "img.tif"
        img.parent.mkdir(parents=True)
        img.write_bytes(b"")
        for name, extra in (("a", "series = 3\n"), ("b", "")):
            (tmp / name).mkdir()
            (tmp / name / "export_definition.cfg").write_text(
                f"[DATA]\nimage = {img}\n{extra}\n[MOVIE]\nfilename = {name}.mp4\n"
                "title = t\ndescription = x\n")
        df = build_config_list(tmp)
        self.assertEqual(sorted(df["image_series"]), [3, 5])
        xlsx = tmp / "c.xlsx"
        df.to_excel(xlsx, sheet_name="Content", index=False)
        edit_config_content(xlsx)
        cp = configparser.ConfigParser()
        cp.read(tmp / "a" / "export_definition.cfg")
        self.assertEqual(cp["DATA"]["series"], "3")
        cp.read(tmp / "b" / "export_definition.cfg")
        self.assertEqual(sorted(build_config_list(tmp)["image_series"]), [3, 5])


if __name__ == '__main__':
    unittest.main()
