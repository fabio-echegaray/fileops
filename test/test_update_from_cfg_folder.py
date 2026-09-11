import tempfile
import unittest
from pathlib import Path

import pandas as pd

from fileops.scripts._config_duplicates import DuplicateEntryError, check_duplicates
from fileops.scripts._config_generate import generate
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

    def test_blank_cfg_folder_across_many_files_is_not_a_duplicate(self):
        # a freshly generated summary has cfg_folder blank in every row; the
        # merge-key check must not treat those as duplicates (regression for
        # the counts-cfg_folder.xlsx false positive)
        self._write_summary({
            "ix":              [0, 1, 2],
            "folder":          [self.img_dir.as_posix()] * 3,
            "filename":        ["movie.nd2", "other.nd2", "third.nd2"],
            "frames":          [10, 10, 10],
            "cfg_path":        ["", "", ""],
            "cfg_folder":      ["", "", ""],
            "image_series_id": [None, None, None],
        })
        self._run_update()

        out = self._read_timeseries()
        self.assertEqual(len(out), 3)

    def test_duplicate_merge_key_in_summary_raises(self):
        # two summary rows with the same (image_path, series) explode the outer
        # merge; the summary side must be checked on the merge key, not cfg_folder
        self._write_summary({
            "ix":              [0, 1],
            "folder":          [self.img_dir.as_posix()] * 2,
            "filename":        ["movie.nd2", "movie.nd2"],
            "frames":          [10, 10],
            "cfg_path":        ["", ""],
            "cfg_folder":      ["", ""],
            "image_series_id": [0, 0],
        })
        with self.assertRaises(DuplicateEntryError):
            self._run_update()

    def test_cfg_folder_shared_by_many_files_is_not_a_duplicate(self):
        # after an update, many images legitimately point at the same config
        # folder; checking duplicates on cfg_folder would break every real
        # update (regression for the counts-cfg_folder.xlsx false positive)
        self._write_summary({
            "ix":              [0, 1],
            "folder":          [self.img_dir.as_posix()] * 2,
            "filename":        ["movie.nd2", "other.nd2"],
            "frames":          [10, 10],
            "cfg_path":        ["", ""],
            "cfg_folder":      [self.cfg_dir.name, self.cfg_dir.name],
            "image_series_id": [0, 0],
        })
        cfg_path = self.cfg_dir / "other.cfg"
        cfg_path.write_text(_cfg_file_text(self.img_dir / "other.nd2", series=0))
        self._run_update()

        out = self._read_timeseries()
        self.assertEqual(len(out), 2)
        self.assertTrue((out["cfg_folder"] == self.cfg_dir.name).all())

    def test_two_config_folders_claiming_same_image_series_raises(self):
        # two distinct config folders each contain a config file for the same
        # image+series: that is an ambiguity, not a shared-folder coincidence
        other_cfg = self.tmp / "cfg" / "exp1b"
        other_cfg.mkdir(parents=True)
        (other_cfg / "movie_dup.cfg").write_text(
            _cfg_file_text(self.img_dir / "movie.nd2", series=0))

        self._write_summary({
            "ix":              [0],
            "folder":          [self.img_dir.as_posix()],
            "filename":        ["movie.nd2"],
            "frames":          [10],
            "cfg_path":        [""],
            "cfg_folder":      [""],
            "image_series_id": [0],
        })
        with self.assertRaises(DuplicateEntryError):
            self._run_update()
        self.assertTrue((self.tmp / "counts-img_ser.xlsx").exists())

    def test_relative_image_path_is_resolved_against_relative_to(self):
        # config files may store the image path relative to a user-provided
        # base (data is often spread across several external disks); the merge
        # must resolve config and summary sides with the same base instead of
        # against the process working directory
        base = self.tmp / "base"
        img_rel = Path("images/movie.nd2")
        cfg_path = self.cfg_dir / "movie.cfg"
        cfg_path.write_text(_cfg_file_text(img_rel, series=0))

        self._write_summary({
            "ix":              [0],
            "folder":          ["images"],
            "filename":        ["movie.nd2"],
            "frames":          [10],
            "cfg_path":        [""],
            "cfg_folder":      [""],
            "image_series_id": [None],
        })
        update_from_cfg_folder(self.summary_path, self.cfg_dir.parent, relative_to=base)

        out = self._read_timeseries()
        self.assertEqual(len(out), 1)
        self.assertEqual(out.loc[0, "cfg_path"], cfg_path.as_posix())

    def test_relative_image_path_without_base_stays_relative(self):
        # no base given: build_config_list must keep the recorded path exactly,
        # never resolving it against the process working directory
        cfg_path = self.cfg_dir / "movie.cfg"
        cfg_path.write_text(_cfg_file_text(Path("images/movie.nd2"), series=0))

        self._write_summary({
            "ix":              [0],
            "folder":          ["images"],
            "filename":        ["movie.nd2"],
            "frames":          [10],
            "cfg_path":        [""],
            "cfg_folder":      [""],
            "image_series_id": [None],
        })
        update_from_cfg_folder(self.summary_path, self.cfg_dir.parent)

        out = self._read_timeseries()
        self.assertEqual(len(out), 1)
        self.assertEqual(out.loc[0, "cfg_path"], cfg_path.as_posix())

    def test_absolute_image_path_kept_as_is(self):
        # absolute config image paths (the common case on a single disk) have
        # always stayed absolute and must continue to do so
        image_path = self.img_dir / "movie.nd2"
        cfg_path = self.cfg_dir / "movie.cfg"
        cfg_path.write_text(_cfg_file_text(image_path, series=0))

        self._write_summary({
            "ix":              [0],
            "folder":          [self.img_dir.as_posix()],
            "filename":        ["movie.nd2"],
            "frames":          [10],
            "cfg_path":        [""],
            "cfg_folder":      [""],
            "image_series_id": [None],
        })
        update_from_cfg_folder(self.summary_path, self.cfg_dir.parent)

        out = self._read_timeseries()
        self.assertEqual(len(out), 1)
        self.assertEqual(out.loc[0, "cfg_path"], cfg_path.as_posix())
        self.assertEqual(out.loc[0, "cfg_folder"], self.cfg_dir.name)

    def test_relative_config_path_matches_as_suffix_without_base(self):
        # configs store image paths relative to their own microscope base, and
        # cannot be resolved against relative_to when none is given; as long as
        # the stored path is a suffix of the summary's absolute image path the
        # config folder must still be located (e.g. T7 disk layout where the
        # summary holds "Fabio/Nikon SoRa (CPF)/..." while configs record
        # "Nikon SoRa (CPF)/...")
        summary_folder = "Fabio/Nikon SoRa (CPF)/20260423 - exp/dish-1"
        cfg_path = self.cfg_dir / "movie.cfg"
        cfg_path.write_text(_cfg_file_text(
            Path("Nikon SoRa (CPF)/20260423 - exp/dish-1/movie.nd2"), series=0))

        self._write_summary({
            "ix":              [0],
            "folder":          [summary_folder],
            "filename":        ["movie.nd2"],
            "frames":          [10],
            "cfg_path":        [""],
            "cfg_folder":      [""],
            "image_series_id": [None],
        })
        update_from_cfg_folder(self.summary_path, self.cfg_dir.parent)

        out = self._read_timeseries()
        self.assertEqual(len(out), 1)
        self.assertEqual(out.loc[0, "cfg_path"], cfg_path.as_posix())
        self.assertEqual(out.loc[0, "cfg_folder"], self.cfg_dir.name)

    def test_relative_config_path_matches_as_suffix_with_shallow_base(self):
        # when relative_to is set to a directory that is *above* the config's
        # real base, the resolved paths differ by one component; the stored
        # relative path still matches as a suffix of the summary image path
        base = self.tmp / "base"
        cfg_path = self.cfg_dir / "movie.cfg"
        cfg_path.write_text(_cfg_file_text(Path("images/movie.nd2"), series=0))

        self._write_summary({
            "ix":              [0],
            "folder":          ["Fabio/images"],
            "filename":        ["movie.nd2"],
            "frames":          [10],
            "cfg_path":        [""],
            "cfg_folder":      [""],
            "image_series_id": [0],
        })
        update_from_cfg_folder(self.summary_path, self.cfg_dir.parent, relative_to=base)

        out = self._read_timeseries()
        self.assertEqual(len(out), 1)
        self.assertEqual(out.loc[0, "cfg_path"], cfg_path.as_posix())
        self.assertEqual(out.loc[0, "cfg_folder"], self.cfg_dir.name)

    def test_suffix_fallback_does_not_override_series(self):
        # the suffix fallback must still respect image_series_id: a config
        # whose series differs from the summary row's must not be attached to
        # that row (the summary row stays unmatched)
        cfg_path = self.cfg_dir / "movie.cfg"
        cfg_path.write_text(_cfg_file_text(
            Path("Nikon SoRa (CPF)/20260423 - exp/dish-1/movie.nd2"), series=0))

        self._write_summary({
            "ix":              [0],
            "folder":          ["Fabio/Nikon SoRa (CPF)/20260423 - exp/dish-1"],
            "filename":        ["movie.nd2"],
            "frames":          [10],
            "cfg_path":        [""],
            "cfg_folder":      [""],
            "image_series_id": [3],
        })
        update_from_cfg_folder(self.summary_path, self.cfg_dir.parent)

        out = self._read_timeseries()
        # the unmatched summary row remains, plus the media-less config appears
        # as its own minimal entry (series 0) in Files-Timeseries
        self.assertEqual(len(out), 2)
        summary_row = out[out["image_series_id"].astype(int) == 3].iloc[0]
        self.assertTrue(pd.isna(summary_row["cfg_path"]) or summary_row["cfg_path"] == "")
        cfg_row = out[out["image_series_id"].astype(int) == 0].iloc[0]
        self.assertEqual(cfg_row["cfg_path"], cfg_path.as_posix())
        self.assertEqual(cfg_row["folder"], "Nikon SoRa (CPF)/20260423 - exp/dish-1")

    def test_suffix_fallback_conflicting_folders_raises(self):
        # two distinct config folders whose stored relative path is a suffix of
        # the same summary image path+series is the same ambiguity the exact
        # match guards against
        other_cfg = self.tmp / "cfg" / "exp1b"
        other_cfg.mkdir(parents=True)
        (other_cfg / "movie_dup.cfg").write_text(_cfg_file_text(
            Path("Nikon SoRa (CPF)/20260423 - exp/dish-1/movie.nd2"), series=0))

        cfg_path = self.cfg_dir / "movie.cfg"
        cfg_path.write_text(_cfg_file_text(
            Path("Nikon SoRa (CPF)/20260423 - exp/dish-1/movie.nd2"), series=0))

        self._write_summary({
            "ix":              [0],
            "folder":          ["Fabio/Nikon SoRa (CPF)/20260423 - exp/dish-1"],
            "filename":        ["movie.nd2"],
            "frames":          [10],
            "cfg_path":        [""],
            "cfg_folder":      [""],
            "image_series_id": [0],
        })
        with self.assertRaises(DuplicateEntryError):
            update_from_cfg_folder(self.summary_path, self.cfg_dir.parent)


def _cfg_file_panel(image_path: Path, series: int = None) -> str:
    """Minimal config with only a DATA section (no MOVIE)."""
    text = f"[DATA]\nimage = {image_path.as_posix()}\n"
    if series is not None:
        text += f"series = {series}\n"
    return text


class TestConfigOnlyRows(unittest.TestCase):
    """Config files whose referenced image was not found in the scanned media
    should still appear as minimal rows in the summary."""
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

    def test_movie_cfg_without_media_appears_in_timeseries(self):
        # a config referencing an image not in the summary should produce a
        # minimal row in Files-Timeseries with folder/filename from the image
        other_img_dir = self.tmp / "other_images"
        other_img_dir.mkdir(parents=True)
        other_cfg_dir = self.tmp / "cfg" / "exp_other"
        other_cfg_dir.mkdir(parents=True)
        cfg_path = other_cfg_dir / "movie.cfg"
        cfg_path.write_text(_cfg_file_text(other_img_dir / "remote_movie.nd2", series=0))

        self._write_summary({
            "ix":              [0],
            "folder":          [self.img_dir.as_posix()],
            "filename":        ["local_movie.nd2"],
            "frames":          [10],
            "cfg_path":        [""],
            "cfg_folder":      [""],
            "image_series_id": [0],
        })
        update_from_cfg_folder(self.summary_path, self.cfg_dir.parent)

        out = self._read_timeseries()
        self.assertEqual(len(out), 2)  # original + config-only row
        cfg_row = out[out["cfg_path"].str.contains("movie.cfg", na=False)].iloc[0]
        self.assertEqual(cfg_row["cfg_path"], cfg_path.as_posix())
        self.assertEqual(cfg_row["cfg_folder"], "exp_other")
        self.assertEqual(cfg_row["filename"], "remote_movie.nd2")
        self.assertEqual(cfg_row["folder"], other_img_dir.as_posix())

    def test_panel_cfg_without_media_appears_in_stills(self):
        # a config with no MOVIE section (panel-only) should land in
        # Files-Stills, not Files-Timeseries
        other_cfg_dir = self.tmp / "cfg" / "exp_panel"
        other_cfg_dir.mkdir(parents=True)
        cfg_path = other_cfg_dir / "panel.cfg"
        cfg_path.write_text(_cfg_file_panel(self.img_dir / "panel_image.tif", series=0))

        self._write_summary({
            "ix":              [0],
            "folder":          [self.img_dir.as_posix()],
            "filename":        ["local_movie.nd2"],
            "frames":          [10],
            "cfg_path":        [""],
            "cfg_folder":      [""],
            "image_series_id": [0],
        })
        update_from_cfg_folder(self.summary_path, self.cfg_dir.parent)

        out_ts = self._read_timeseries()
        out_stills = pd.read_excel(self.summary_path, sheet_name="Files-Stills")
        self.assertEqual(len(out_ts), 1)  # original only
        self.assertEqual(len(out_stills), 1)  # panel-only row
        cfg_row = out_stills.iloc[0]
        self.assertEqual(cfg_row["cfg_path"], cfg_path.as_posix())
        self.assertEqual(cfg_row["cfg_folder"], "exp_panel")
        self.assertEqual(cfg_row["filename"], "panel_image.tif")

    def test_movie_cfg_only_row_does_not_leak_into_stills(self):
        # regression: when no panel definitions exist, Files-Stills must stay
        # empty. has_movie is object-dtype after the outer merge and
        # ~has_movie on an object Series yields -2 (truthy), which previously
        # routed movie config-only rows into Files-Stills.
        other_img_dir = self.tmp / "other_images"
        other_img_dir.mkdir(parents=True)
        other_cfg_dir = self.tmp / "cfg" / "exp_other"
        other_cfg_dir.mkdir(parents=True)
        cfg_other = other_cfg_dir / "remote.cfg"
        cfg_other.write_text(_cfg_file_text(other_img_dir / "remote.nd2", series=0))

        self._write_summary({
            "ix":              [0],
            "folder":          [self.img_dir.as_posix()],
            "filename":        ["local.nd2"],
            "frames":          [5],
            "cfg_path":        [""],
            "cfg_folder":      [""],
            "image_series_id": [0],
        })
        update_from_cfg_folder(self.summary_path, self.cfg_dir.parent)

        out = self._read_timeseries()
        self.assertEqual(len(out), 2)  # original + config-only row
        stills = pd.read_excel(self.summary_path, sheet_name="Files-Stills")
        self.assertEqual(len(stills), 0)

    def test_config_only_rows_coexist_with_matched_rows(self):
        # a mix of media-matched and media-unmatched configs should all appear
        other_img_dir = self.tmp / "other_images"
        other_img_dir.mkdir(parents=True)
        other_cfg_dir = self.tmp / "cfg" / "exp_other"
        other_cfg_dir.mkdir(parents=True)
        cfg_other = other_cfg_dir / "remote.cfg"
        cfg_other.write_text(_cfg_file_text(other_img_dir / "remote.nd2", series=0))

        cfg_local = self.cfg_dir / "local.cfg"
        cfg_local.write_text(_cfg_file_text(self.img_dir / "local.nd2", series=0))

        self._write_summary({
            "ix":              [0],
            "folder":          [self.img_dir.as_posix()],
            "filename":        ["local.nd2"],
            "frames":          [5],
            "cfg_path":        [""],
            "cfg_folder":      [""],
            "image_series_id": [0],
        })
        update_from_cfg_folder(self.summary_path, self.cfg_dir.parent)

        out = self._read_timeseries()
        self.assertEqual(len(out), 2)
        # the media-matched row has real frames; the config-only row has no
        # frame count to report
        local_row = out[out["cfg_path"].str.contains("local.cfg", na=False)].iloc[0]
        self.assertEqual(local_row["frames"], 5)
        remote_row = out[out["cfg_path"].str.contains("remote.cfg", na=False)].iloc[0]
        self.assertTrue(pd.isna(remote_row["frames"]))

    def test_series_is_preserved_for_config_only_rows(self):
        # a config-only row should carry the series id from the DATA section
        other_img_dir = self.tmp / "other_images"
        other_img_dir.mkdir(parents=True)
        other_cfg_dir = self.tmp / "cfg" / "exp_other"
        other_cfg_dir.mkdir(parents=True)
        cfg_path = other_cfg_dir / "movie.cfg"
        cfg_path.write_text(_cfg_file_text(other_img_dir / "remote.nd2", series=7))

        self._write_summary({
            "ix":              [0],
            "folder":          [self.img_dir.as_posix()],
            "filename":        ["local.nd2"],
            "frames":          [10],
            "cfg_path":        [""],
            "cfg_folder":      [""],
            "image_series_id": [0],
        })
        update_from_cfg_folder(self.summary_path, self.cfg_dir.parent)

        out = self._read_timeseries()
        remote_row = out[out["cfg_path"].str.contains("movie.cfg", na=False)].iloc[0]
        self.assertEqual(int(remote_row["image_series_id"]), 7)

    def test_already_associated_config_is_not_double_listed(self):
        # a config whose cfg_path already appears on a media row (from a prior
        # sync) must not also be emitted as a media-less config-only row
        cfg_path = self.cfg_dir / "movie.cfg"
        cfg_path.write_text(_cfg_file_text(
            Path("Nikon SoRa (CPF)/20260423 - exp/dish-1/movie.nd2"), series=0))

        self._write_summary({
            "ix":              [0],
            "folder":          ["Fabio/Nikon SoRa (CPF)/20260423 - exp/dish-1"],
            "filename":        ["movie.nd2"],
            "frames":          [10],
            "cfg_path":        [cfg_path.as_posix()],
            "cfg_folder":      ["exp1"],
            "image_series_id": [0],
        })
        update_from_cfg_folder(self.summary_path, self.cfg_dir.parent)

        out = self._read_timeseries()
        self.assertEqual(len(out), 1)
        self.assertEqual(out.loc[0, "cfg_path"], cfg_path.as_posix())
        self.assertEqual(out.loc[0, "cfg_folder"], "exp1")

    def test_unassociated_media_and_config_only_row(self):
        # a media row with no config + a genuinely media-less config must both
        # survive as separate entries
        other_img_dir = self.tmp / "other_images"
        other_img_dir.mkdir(parents=True)
        other_cfg_dir = self.tmp / "cfg" / "exp_other"
        other_cfg_dir.mkdir(parents=True)
        cfg_other = other_cfg_dir / "remote.cfg"
        cfg_other.write_text(_cfg_file_text(other_img_dir / "remote.nd2", series=0))

        self._write_summary({
            "ix":              [0],
            "folder":          [self.img_dir.as_posix()],
            "filename":        ["local.nd2"],
            "frames":          [10],
            "cfg_path":        [""],
            "cfg_folder":      [""],
            "image_series_id": [0],
        })
        update_from_cfg_folder(self.summary_path, self.cfg_dir.parent)

        out = self._read_timeseries()
        self.assertEqual(len(out), 2)
        local_row = out[out["filename"] == "local.nd2"].iloc[0]
        self.assertTrue(pd.isna(local_row["cfg_path"]) or local_row["cfg_path"] == "")
        remote_row = out[out["cfg_path"].str.contains("remote.cfg", na=False)].iloc[0]
        self.assertEqual(remote_row["cfg_folder"], "exp_other")


class TestCheckDuplicates(unittest.TestCase):
    def test_blank_values_are_not_duplicates(self):
        # a freshly generated summary has cfg_folder blank ('') in many rows;
        # those are "not filled in", not a duplicated value (regression for the
        # counts-cfg_folder.xlsx false positive on the update flow)
        df = pd.DataFrame({
            "cfg_folder": [""] * 38,
            "ix":         list(range(38)),
        })
        check_duplicates(df, "cfg_folder")

    def test_nan_values_are_not_duplicates(self):
        df = pd.DataFrame({
            "cfg_folder": [float("nan")] * 5,
            "ix":         list(range(5)),
        })
        check_duplicates(df, "cfg_folder")

    def test_mixed_blank_and_value_are_not_duplicates(self):
        df = pd.DataFrame({
            "cfg_folder": ["", "", "exp1", "exp2"],
            "ix":         list(range(4)),
        })
        check_duplicates(df, "cfg_folder")

    def test_real_duplicates_still_raise(self):
        df = pd.DataFrame({
            "cfg_folder": ["exp1", "exp1", "exp2", "exp3"],
            "ix":         list(range(4)),
        })
        with self.assertRaises(DuplicateEntryError):
            check_duplicates(df, "cfg_folder")

    def test_single_blank_across_many_unique_values_ok(self):
        df = pd.DataFrame({
            "cfg_folder": [""] + [f"exp{i}" for i in range(20)],
            "ix":         list(range(21)),
        })
        check_duplicates(df, "cfg_folder")


class TestGenerateConfig(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.base = self.tmp / "base"
        self.base.mkdir(parents=True)
        self.img = self.base / "Microscope" / "imgs" / "movie.nd2"
        self.img.parent.mkdir(parents=True)
        self.img.write_bytes(b"fake")
        self.summary_path = self.tmp / "summary.xlsx"
        self.out = self.tmp / "out"

    def tearDown(self):
        self._tmp.cleanup()

    def _write_summary(self, rows, channels=None):
        df = pd.DataFrame(rows)
        ch = pd.DataFrame(channels or [{"name": "c1", "color": "white"}])
        with pd.ExcelWriter(self.summary_path, engine="openpyxl") as writer:
            ch.to_excel(writer, sheet_name="Channels", index=False)
            df.to_excel(writer, sheet_name="Files-Timeseries", index=False)

    def test_relative_folder_resolves_against_relative_to(self):
        # folder is stored relative to relative_to; generate must resolve it
        # there for the mtime + cfg creation (regression: FileNotFoundError on
        # a relative path resolved against the CWD)
        self._write_summary({
            "folder":    ["Microscope/imgs"],
            "filename":  ["movie.nd2"],
            "cfg_folder":["exp1"],
            "cfg_path":  [""],
            "image_id":  ["Image:3"],
            "channel_names": ["['c1']"],
        })
        df = generate(self.summary_path, self.out, relative_to=self.base)
        cfg = self.out / "exp1" / "export_definition.cfg"
        self.assertTrue(cfg.exists())
        self.assertTrue("image = Microscope/imgs/movie.nd2" in cfg.read_text())
        self.assertEqual(df.loc[0, "cfg_path"], cfg.as_posix())

    def test_missing_source_image_is_skipped_not_crash(self):
        # a source image that does not exist must be skipped with a warning
        # instead of aborting the whole generation loop
        self._write_summary({
            "folder":    ["Microscope/imgs", "Microscope/imgs"],
            "filename":  ["movie.nd2", "missing.nd2"],
            "cfg_folder":["exp1", "exp2"],
            "cfg_path":  ["", ""],
            "image_id":  ["Image:3", "Image:4"],
            "channel_names": ["['c1']", "['c1']"],
        })
        generate(self.summary_path, self.out, relative_to=self.base)
        self.assertTrue((self.out / "exp1" / "export_definition.cfg").exists())
        self.assertFalse((self.out / "exp2" / "export_definition.cfg").exists())

    def test_generated_cfg_path_can_be_assigned_back_to_string_column(self):
        # assigning a Path into the pandas string column must not raise
        # "TypeError: len() of unsized object"
        self._write_summary({
            "folder":    ["Microscope/imgs"],
            "filename":  ["movie.nd2"],
            "cfg_folder":["exp1"],
            "cfg_path":  [""],
            "image_id":  ["Image:3"],
            "channel_names": ["[]"],
        })
        generate(self.summary_path, self.out, relative_to=self.base)
        cfg = self.out / "exp1" / "export_definition.cfg"
        self.assertTrue(cfg.exists())


if __name__ == '__main__':
    unittest.main()
