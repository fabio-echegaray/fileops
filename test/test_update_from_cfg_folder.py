import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from fileops.scripts._config_duplicates import DuplicateEntryError, check_duplicates
from fileops.scripts._config_generate import generate
from fileops.scripts._config_map import (
    read_config_map,
    rename_config_folders,
    sync_config_map,
    write_config_map,
)


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
        self.content_path = self.tmp / "cfg_content.xlsx"

    def tearDown(self):
        self._tmp.cleanup()

    def _write_summary(self, rows, channels=None):
        df = pd.DataFrame(rows)
        ch = pd.DataFrame(channels or [{"name": "c1", "color": "white"}])
        with pd.ExcelWriter(self.summary_path, engine="openpyxl") as writer:
            ch.to_excel(writer, sheet_name="Channels", index=False)
            df.to_excel(writer, sheet_name="Files-Timeseries", index=False)

    def _write_registry(self, rows):
        write_config_map(self.content_path, pd.DataFrame(rows))

    def test_relative_folder_resolves_against_relative_to(self):
        # folder is stored relative to relative_to; generate must resolve it
        # there for the mtime + cfg creation (regression: FileNotFoundError on
        # a relative path resolved against the CWD). The cfg_folder comes from
        # the Configs registry, the media metadata from the summary.
        self._write_summary({
            "folder":        ["Microscope/imgs"],
            "filename":      ["movie.nd2"],
            "image_id":      ["Image:3"],
            "channel_names": ["['c1']"],
        })
        self._write_registry([{
            "cfg_folder": "exp1", "cfg_path": "",
            "image_path": "Microscope/imgs/movie.nd2",
            "image_series_id": 0, "has_movie": False,
        }])
        generate(self.summary_path, self.out, relative_to=self.base)
        cfg = self.out / "exp1" / "export_definition.cfg"
        self.assertTrue(cfg.exists())
        self.assertIn("image = Microscope/imgs/movie.nd2", cfg.read_text())

    def test_missing_source_image_is_skipped_not_crash(self):
        # a source image that does not exist must be skipped with a warning
        # instead of aborting the whole generation loop
        self._write_summary({
            "folder":        ["Microscope/imgs", "Microscope/imgs"],
            "filename":      ["movie.nd2", "missing.nd2"],
            "image_id":      ["Image:3", "Image:4"],
            "channel_names": ["['c1']", "['c1']"],
        })
        self._write_registry([
            {"cfg_folder": "exp1", "cfg_path": "", "image_path": "Microscope/imgs/movie.nd2",
             "image_series_id": 0, "has_movie": False},
            {"cfg_folder": "exp2", "cfg_path": "", "image_path": "Microscope/imgs/missing.nd2",
             "image_series_id": 0, "has_movie": False},
        ])
        generate(self.summary_path, self.out, relative_to=self.base)
        self.assertTrue((self.out / "exp1" / "export_definition.cfg").exists())
        self.assertFalse((self.out / "exp2" / "export_definition.cfg").exists())

    def test_generated_cfg_path_can_be_assigned_back_to_string_column(self):
        # assigning a Path into the pandas string column must not raise
        # "TypeError: len() of unsized object"
        self._write_summary({
            "folder":        ["Microscope/imgs"],
            "filename":      ["movie.nd2"],
            "image_id":      ["Image:3"],
            "channel_names": ["[]"],
        })
        self._write_registry([{
            "cfg_folder": "exp1", "cfg_path": "",
            "image_path": "Microscope/imgs/movie.nd2",
            "image_series_id": 0, "has_movie": False,
        }])
        generate(self.summary_path, self.out, relative_to=self.base)
        self.assertTrue((self.out / "exp1" / "export_definition.cfg").exists())

    def test_existing_cfg_is_left_untouched(self):
        # a registry row that already points at a cfg file must not be rewritten
        existing = self.out / "exp1" / "export_definition.cfg"
        existing.parent.mkdir(parents=True)
        existing.write_text("sentinel")
        self._write_summary({
            "folder":        ["Microscope/imgs"],
            "filename":      ["movie.nd2"],
            "image_id":      ["Image:3"],
            "channel_names": ["['c1']"],
        })
        self._write_registry([{
            "cfg_folder": "exp1", "cfg_path": existing.as_posix(),
            "image_path": "Microscope/imgs/movie.nd2",
            "image_series_id": 0, "has_movie": True,
        }])
        generate(self.summary_path, self.out, relative_to=self.base)
        self.assertEqual(existing.read_text(), "sentinel")

    def test_generate_uses_relative_to_to_resolve_image_paths(self):
        base = self.tmp / "base2"
        image_dir = base / "Microscope" / "Nikon SoRa (CPF)" / "20260712 - test"
        image_dir.mkdir(parents=True)
        (image_dir / "RpLP2.nd2").write_bytes(b"fake nd2")

        summary_path = self.tmp / "summary2.xlsx"
        with pd.ExcelWriter(summary_path, engine="openpyxl") as writer:
            pd.DataFrame([
                {
                    "ix":            0,
                    "folder":        "Microscope/Nikon SoRa (CPF)/20260712 - test",
                    "filename":      "RpLP2.nd2",
                    "image_id":      "Image:0",
                    "channel_names": "['60x GFP']",
                }
            ]).to_excel(writer, sheet_name="Files-Timeseries", index=False)
            pd.DataFrame([
                {"name": "60x GFP", "color": "green"}
            ]).to_excel(writer, sheet_name="Channels", index=False)

        content_path = self.tmp / "cfg_content.xlsx"
        write_config_map(content_path, pd.DataFrame([{
            "cfg_folder": "dsRNA-RpLP2-2X01", "cfg_path": "",
            "image_path": "Microscope/Nikon SoRa (CPF)/20260712 - test/RpLP2.nd2",
            "image_series_id": 0, "has_movie": False,
        }]))

        exp_path = self.tmp / "export"
        generate(summary_path, exp_path, relative_to=base, content_path=content_path)

        cfg_path = exp_path / "dsRNA-RpLP2-2X01" / "export_definition.cfg"
        self.assertTrue(cfg_path.exists())


class TestCheckDuplicates(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

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
            check_duplicates(df, "cfg_folder", lst_path=self.tmp / "report.xlsx")
        self.assertTrue((self.tmp / "counts-cfg_folder.xlsx").exists())

    def test_single_blank_across_many_unique_values_ok(self):
        df = pd.DataFrame({
            "cfg_folder": [""] + [f"exp{i}" for i in range(20)],
            "ix":         list(range(21)),
        })
        check_duplicates(df, "cfg_folder")


class TestConfigUpdateFlow(unittest.TestCase):
    """The registry flow must survive real-life frames.

    Several image series legitimately share a single configuration folder (each
    with its own config file); syncing and renaming must not abort, and the
    flow needs no summary at all.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.img_dir = self.tmp / "images"
        self.exp_dir = self.tmp / "export"
        self.cfg_dir = self.exp_dir / "exp1"
        self.cfg_dir.mkdir(parents=True)

    def tearDown(self):
        self._tmp.cleanup()

    def _write_cfg(self, path: Path, image: Path, series: int = 0):
        path.write_text(
            f"[DATA]\nimage = {image.as_posix()}\nseries = {series}\n\n"
            "[MOVIE-1]\ntitle = t\ndescription = d\nfilename = m\nfps = 10\nlayout = twoch\n")

    def test_shared_cfg_folder_and_no_description_column(self):
        # two image series in the same experiment folder, each with its own
        # config file. This is the data shape that crashed the GUI update with
        # KeyError: 'description' and then DuplicateEntryError on the shared
        # cfg_folder. The registry flow must tolerate it without any summary.
        img_a = self.img_dir / "c1" / "a.nd2"
        img_b = self.img_dir / "c1" / "b.nd2"
        img_a.parent.mkdir(parents=True, exist_ok=True)
        img_b.parent.mkdir(parents=True, exist_ok=True)
        img_a.write_bytes(b"fake")
        img_b.write_bytes(b"fake")

        cfg_a = self.cfg_dir / "export_definition.cfg"
        cfg_b = self.cfg_dir / "export_definition copy.cfg"
        self._write_cfg(cfg_a, img_a, series=0)
        self._write_cfg(cfg_b, img_b, series=0)

        content_path = self.tmp / "cfg_content.xlsx"
        sync_config_map(content_path, self.exp_dir)
        rename_config_folders(content_path, self.exp_dir)

        df = read_config_map(content_path)
        self.assertEqual(len(df), 2)
        self.assertEqual(set(df["cfg_folder"]), {"exp1"})
        self.assertTrue(cfg_a.exists())
        self.assertTrue(cfg_b.exists())

    def test_renaming_cfg_folder_moves_nested_config_and_updates_moviefile(self):
        # configs live nested under a microscope tree, e.g.
        # .../<scope>/<strain>/<cfg_folder>/export_definition.cfg. Editing
        # cfg_folder in the Configs registry must move the config file into a
        # new folder *at the same nesting depth* (keeping the scope/strain
        # path), and rename the MOVIE filename field so the output file stems
        # follow the new folder. The rendered movie file itself must not be
        # touched. Regression for both the ini_path-collapse bug (all 275 rows
        # looked like a rename) and the image-loading guard that silently
        # skipped every rename.
        strain_dir = self.exp_dir / "Microscope" / "Nikon (CPF)" / "NG-Sas6-KI-Sqh-mCh"
        cfg_dir = strain_dir / "supernatant-1002"
        cfg_dir.mkdir(parents=True)

        img = self.img_dir / "c1" / "a.nd2"
        img.parent.mkdir(parents=True, exist_ok=True)
        img.write_bytes(b"fake")

        cfg_path = cfg_dir / "export_definition.cfg"
        cfg_path.write_text(
            f"[DATA]\nimage = {img.as_posix()}\nseries = 0\n\n"
            "[MOVIE-1]\ntitle = t\ndescription = 1hr collection, 2hr incubation\n"
            "filename = 20230726-supernatant-1002\nfps = 10\nlayout = twoch\n")
        (cfg_dir / "20230726-supernatant-1002.twoch.mp4").write_bytes(b"rendered")

        content_path = self.tmp / "cfg_content.xlsx"
        sync_config_map(content_path, self.exp_dir)
        # unchanged cfg_folder -> config must not move
        rename_config_folders(content_path, self.exp_dir)
        self.assertTrue(cfg_path.exists())
        self.assertFalse((strain_dir / "export_definition.cfg").exists())

        # now the user edits cfg_folder in the registry
        df = read_config_map(content_path)
        df.loc[df["cfg_path"] == cfg_path.as_posix(), "cfg_folder"] = "supernatant-1002-v2"
        write_config_map(content_path, df)

        renamed = rename_config_folders(content_path, self.exp_dir)

        new_cfg = strain_dir / "supernatant-1002-v2" / "export_definition.cfg"
        self.assertFalse(cfg_path.exists())
        self.assertTrue(new_cfg.exists())
        text = new_cfg.read_text()
        self.assertIn("filename = 20230726-supernatant-1002-v2", text)
        self.assertNotIn("filename = 20230726-supernatant-1002\n", text)
        # registry now points at the moved file
        row = renamed[renamed["cfg_path"] == new_cfg.as_posix()]
        self.assertEqual(len(row), 1)
        self.assertEqual(row.iloc[0]["cfg_folder"], "supernatant-1002-v2")
        # rendered file stays where it was, not renamed
        self.assertTrue((cfg_dir / "20230726-supernatant-1002.twoch.mp4").exists())
        self.assertFalse((strain_dir / "supernatant-1002-v2" / "20230726-supernatant-1002-v2.twoch.mp4").exists())

    def test_renaming_config_folders_with_relative_to_matches_and_moves(self):
        # regression for the GUI update flow: the summary stores folder
        # relative to a user base path (relative_to), and config files store
        # their image path the same way. sync_config_map() must resolve the
        # cfg image path against relative_to so the registry row matches the
        # media, and rename_config_folders() must still move the file.
        base = self.tmp / "base"
        scope_dir = base / "Nikon SoRA (CPF)" / "20250508" / "dish-1"
        strain_dir = self.exp_dir / "Microscope" / "Nikon (CPF)" / "NG-Sas6-KI-Sqh-mCh"
        cfg_dir = strain_dir / "supernatant-1002"
        cfg_dir.mkdir(parents=True)

        img = scope_dir / "a.nd2"
        img.parent.mkdir(parents=True, exist_ok=True)
        img.write_bytes(b"fake")

        cfg_path = cfg_dir / "export_definition.cfg"
        cfg_path.write_text(
            f"[DATA]\nimage = {img.relative_to(base).as_posix()}\nseries = 0\n\n"
            "[MOVIE-1]\ntitle = t\ndescription = 1hr collection, 2hr incubation\n"
            "filename = 20230726-supernatant-1002\nfps = 10\nlayout = twoch\n")

        content_path = self.tmp / "cfg_content.xlsx"
        sync_config_map(content_path, self.exp_dir, relative_to=base)

        df = read_config_map(content_path)
        self.assertEqual(len(df), 1)
        self.assertEqual(df.iloc[0]["image_path"],
                         "Nikon SoRA (CPF)/20250508/dish-1/a.nd2")
        df.loc[df["cfg_path"] == cfg_path.as_posix(), "cfg_folder"] = "supernatant-1002-v2"
        write_config_map(content_path, df)

        rename_config_folders(content_path, self.exp_dir, relative_to=base)

        new_cfg = strain_dir / "supernatant-1002-v2" / "export_definition.cfg"
        self.assertFalse(cfg_path.exists())
        self.assertTrue(new_cfg.exists())
        self.assertIn("filename = 20230726-supernatant-1002-v2", new_cfg.read_text())

    def test_git_rename_shows_as_rename_with_caller_in_other_repo(self):
        # The GUI calls the rename from its *own* repository working
        # directory while the configs live in a *different* repository (the
        # export tree). A bare `git mv <abs> <abs>` run from the GUI's repo
        # fails with "is outside repository", so every rename silently degraded
        # to a plain os.rename and git presented the move as a delete + add.
        # git must be pinned (via -C) to the config's own folder so the config
        # repository is found and the move is recorded as a rename.
        if shutil.which("git") is None:
            self.skipTest("git not available")

        export_repo = self.tmp / "export_repo"
        strain_dir = export_repo / "Microscope" / "Nikon (CPF)" / "NG-Sas6-KI-Sqh-mCh"
        cfg_dir = strain_dir / "supernatant-1002"
        cfg_dir.mkdir(parents=True)

        img = self.img_dir / "c1" / "a.nd2"
        img.parent.mkdir(parents=True, exist_ok=True)
        img.write_bytes(b"fake")

        cfg_path = cfg_dir / "export_definition.cfg"
        self._write_cfg(cfg_path, img, series=0)

        def git(*args):
            return subprocess.run(["git", *args], capture_output=True,
                                  text=True, cwd=export_repo)

        init = git("init", "-q")
        self.assertEqual(init.returncode, 0)
        git("config", "user.email", "test@example.com")
        git("config", "user.name", "test")
        git("add", ".")
        git("commit", "-qm", "init")
        self.assertIn("supernatant-1002", git("ls-files").stdout)

        content_path = self.tmp / "cfg_content.xlsx"
        sync_config_map(content_path, export_repo)
        df = read_config_map(content_path)
        self.assertEqual(df.iloc[0]["cfg_folder"], "supernatant-1002")
        df.loc[df["cfg_path"] == cfg_path.as_posix(), "cfg_folder"] = "supernatant-1002-v2"
        write_config_map(content_path, df)

        # simulate the GUI: run the rename from a different directory (its
        # own repo) so a non -C git mv would fail "outside repository"
        prev = os.getcwd()
        other_repo = self.tmp / "caller_repo"
        other_repo.mkdir(exist_ok=True)
        os.chdir(other_repo)
        try:
            rename_config_folders(content_path, export_repo)
        finally:
            os.chdir(prev)

        new_cfg = strain_dir / "supernatant-1002-v2" / "export_definition.cfg"
        self.assertFalse(cfg_path.exists())
        self.assertTrue(new_cfg.exists())

        status = git("status", "--short").stdout
        self.assertIn("supernatant-1002", status)
        rename_line = [l for l in status.splitlines()
                       if "supernatant-1002-v2" in l] if status else []
        self.assertTrue(rename_line,
                        msg=f"expected a rename in git status, got:\n{status}")
        self.assertTrue(rename_line[0].startswith("R"),
                        msg=f"expected rename (R), got:\n{status}")


if __name__ == '__main__':
    unittest.main()