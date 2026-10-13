import tempfile
import unittest
from pathlib import Path

import pandas as pd

from fileops.scripts._config_map import (
    build_config_map,
    read_config_map,
    rename_config_folders,
    sync_config_map,
    write_config_map,
)


def _cfg_text(image_path, series=0, movie_sections=1, filename="movie"):
    text = f"[DATA]\nimage = {image_path.as_posix()}\nseries = {series}\n"
    for i in range(1, movie_sections + 1):
        text += (
            f"\n[MOVIE-{i}]\n"
            "title = t\n"
            "description = 1hr collection, 2hr incubation\n"
            f"filename = {filename}\n"
            "fps = 10\n"
            "layout = twoch\n"
        )
    return text


class TestConfigMapBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.cfg_root = self.tmp / "export"
        self.cfg_root.mkdir(parents=True)
        self.content_path = self.tmp / "cfg_content.xlsx"

    def tearDown(self):
        self._tmp.cleanup()

    def _add_cfg(self, name, relative_image, series=0, movie_sections=1,
                 parent=(), image_subtree=None, filename="movie"):
        folder = self.cfg_root.joinpath(*parent)
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / name
        if image_subtree is None:
            image_subtree = folder
        img = Path(image_subtree) / relative_image
        path.write_text(_cfg_text(img, series=series, movie_sections=movie_sections,
                                  filename=filename))
        return path

    def _row_by_cfg(self, df, cfg_path):
        mask = df["cfg_path"] == cfg_path.as_posix()
        self.assertEqual(mask.sum(), 1)
        return df[mask].iloc[0]

    def _write_summary(self, path, rows):
        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            pd.DataFrame({"name": ["ch1"]}).to_excel(writer, sheet_name="Channels", index=False)
            pd.DataFrame(rows).to_excel(writer, sheet_name="Files-Timeseries", index=False)


class TestBuildConfigMap(TestConfigMapBase):

    def test_one_row_per_cfg_file(self):
        cfg_a = self._add_cfg("export_definition.cfg", "a.nd2", parent=("scope", "strain", "exp1"))
        cfg_b = self._add_cfg("second.cfg", "b.nd2", parent=("other", "exp2"))

        df = build_config_map(self.cfg_root)

        self.assertEqual(len(df), 2)
        self.assertEqual(set(df["cfg_path"]), {cfg_a.as_posix(), cfg_b.as_posix()})
        for _, row in df.iterrows():
            self.assertIn("cfg_folder", row.index)
            self.assertIn("image_path", row.index)
            self.assertIn("image_series_id", row.index)
            self.assertNotIn("has_movie", row.index)

    def test_multi_movie_cfg_is_collapsed_to_one_row(self):
        cfg = self._add_cfg("export_definition.cfg", "a.nd2", movie_sections=2)

        df = build_config_map(self.cfg_root)

        self.assertEqual(len(df), 1)
        self.assertEqual(self._row_by_cfg(df, cfg)["cfg_path"], cfg.as_posix())

    def test_panel_only_cfg_still_emits_row(self):
        cfg_dir = self.cfg_root / "panel"
        cfg_dir.mkdir(parents=True)
        cfg = cfg_dir / "export_definition.cfg"
        cfg.write_text("[DATA]\nimage = c.nd2\n")

        df = build_config_map(self.cfg_root)

        self.assertEqual(len(df), 1)
        row = self._row_by_cfg(df, cfg)
        self.assertEqual(row["cfg_folder"], "panel")
        self.assertTrue(row["image_path"].endswith("c.nd2"))

    def test_relative_to_resolves_image_paths(self):
        base = self.tmp / "base"
        self._add_cfg("export_definition.cfg", "a.nd2",
                      image_subtree=base / "scope", parent=("exp1",))

        df = build_config_map(self.cfg_root, relative_to=base)

        row = df.iloc[0]
        self.assertEqual(row["image_path"], "scope/a.nd2")

    def test_recursive_discovery_skips_non_cfg_files(self):
        # cfgs nested at several depths must all be collected; non-'.cfg' and
        # AppleDouble '._' files must not
        top = self._add_cfg("top.cfg", "top.nd2")
        nested = self._add_cfg("export_definition.cfg", "a.nd2",
                               parent=("Microscope", "Nikon (CPF)", "NG-Sas6", "dish-1"))
        sibling = self._add_cfg("export_definition.cfg", "b.nd2",
                                parent=("Microscope", "Nikon (CPF)", "NG-Sas6", "dish-2"))
        deep = self._add_cfg("deep.cfg", "d.nd2", parent=("a", "b", "c", "d", "e"))
        (top.parent / "notes.txt").write_text("not a config")
        (nested.parent.parent / "._phantom.cfg").write_bytes(b"appledouble")

        df = build_config_map(self.cfg_root)

        self.assertEqual(set(df["cfg_path"]),
                         {p.as_posix() for p in (top, nested, sibling, deep)})

    def test_cfg_inherits_missing_data_from_parent_defaults(self):
        # a config that omits [DATA] must inherit it from a defaults.cfg in an
        # ancestor folder, and the defaults file itself must not become a row.
        proj = self.cfg_root / "scope" / "proj"
        proj.mkdir(parents=True)
        default_image = proj / "img.nd2"
        (self.cfg_root / "defaults.cfg").write_text(
            f"[DATA]\nimage = {default_image.as_posix()}\nseries = 3\n")
        cfg_dir = proj / "exp1"
        cfg_dir.mkdir()
        cfg = cfg_dir / "export_definition.cfg"
        cfg.write_text("[MOVIE]\ntitle = t\ndescription = d\nfilename = m\n")

        df = build_config_map(self.cfg_root)

        self.assertEqual(set(df["cfg_path"]), {cfg.as_posix()})
        row = self._row_by_cfg(df, cfg)
        self.assertEqual(row["image_series_id"], 3)
        self.assertEqual(row["image_path"], default_image.as_posix())

    def test_explicit_cfg_values_override_defaults(self):
        proj = self.cfg_root / "scope" / "proj"
        proj.mkdir(parents=True)
        (self.cfg_root / "defaults.cfg").write_text(
            f"[DATA]\nimage = {(proj / 'default.nd2').as_posix()}\nseries = 1\n")
        cfg = self._add_cfg("export_definition.cfg", "own.nd2", series=9,
                            parent=("scope", "proj", "exp1"), image_subtree=proj / "exp1")

        df = build_config_map(self.cfg_root)

        row = self._row_by_cfg(df, cfg)
        self.assertEqual(row["image_series_id"], 9)
        self.assertTrue(row["image_path"].endswith("own.nd2"))

    def test_closest_defaults_file_wins(self):
        proj = self.cfg_root / "scope" / "proj"
        proj.mkdir(parents=True)
        (self.cfg_root / "defaults.cfg").write_text(
            f"[DATA]\nimage = {(self.cfg_root / 'top.nd2').as_posix()}\nseries = 1\n")
        (proj / "defaults.cfg").write_text(
            f"[DATA]\nimage = {(proj / 'near.nd2').as_posix()}\nseries = 2\n")
        cfg_dir = proj / "exp1"
        cfg_dir.mkdir()
        cfg = cfg_dir / "export_definition.cfg"
        cfg.write_text("[MOVIE]\ntitle = t\ndescription = d\nfilename = m\n")

        df = build_config_map(self.cfg_root)

        row = self._row_by_cfg(df, cfg)
        self.assertEqual(row["image_series_id"], 2)
        self.assertTrue(row["image_path"].endswith("near.nd2"))



class TestConfigRegistryIO(TestConfigMapBase):

    def test_write_read_config_map_roundtrip(self):
        cfg = self._add_cfg("export_definition.cfg", "a.nd2", parent=("exp1",))
        df = build_config_map(self.cfg_root)

        write_config_map(self.content_path, df)
        out = read_config_map(self.content_path)

        self.assertEqual(len(out), 1)
        row = out.iloc[0]
        self.assertEqual(row["cfg_path"], cfg.as_posix())
        self.assertEqual(row["cfg_folder"], "exp1")

    def test_write_config_map_preserves_content_sheet(self):
        with pd.ExcelWriter(self.content_path, engine="openpyxl") as writer:
            pd.DataFrame({"cfg_path": ["x.cfg"], "title": ["keep"]}).to_excel(
                writer, sheet_name="Content", index=False)
        df = build_config_map(self.cfg_root)

        write_config_map(self.content_path, df)

        content = pd.read_excel(self.content_path, sheet_name="Content")
        self.assertEqual(content.loc[0, "title"], "keep")
        self.assertEqual(len(read_config_map(self.content_path)), 0)

    def test_read_config_map_missing_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            read_config_map(self.tmp / "missing.xlsx")


class TestSyncConfigMap(TestConfigMapBase):

    def test_sync_preserves_user_cfg_folder_edit(self):
        cfg = self._add_cfg("export_definition.cfg", "a.nd2", parent=("exp1",))
        sync_config_map(self.content_path, self.cfg_root)

        df = read_config_map(self.content_path)
        df.loc[df["cfg_path"] == cfg.as_posix(), "cfg_folder"] = "renamed-by-user"
        write_config_map(self.content_path, df)

        sync_config_map(self.content_path, self.cfg_root)
        out = read_config_map(self.content_path)

        row = self._row_by_cfg(out, cfg)
        self.assertEqual(row["cfg_folder"], "renamed-by-user")

    def test_new_cfg_file_gets_its_actual_folder_name(self):
        self._add_cfg("export_definition.cfg", "a.nd2", parent=("exp1",))
        sync_config_map(self.content_path, self.cfg_root)
        self._add_cfg("fresh.cfg", "b.nd2", parent=("new-exp",))

        sync_config_map(self.content_path, self.cfg_root)
        out = read_config_map(self.content_path)

        self.assertEqual(len(out), 2)
        fresh = self._row_by_cfg(out, self.cfg_root / "new-exp" / "fresh.cfg")
        self.assertEqual(fresh["cfg_folder"], "new-exp")

    def test_summary_rows_without_cfg_become_candidates(self):
        self._add_cfg("export_definition.cfg", "a.nd2", series=0, parent=("exp1",))
        summary = self.tmp / "summary.xlsx"
        self._write_summary(summary, {
            "folder":          [self.cfg_root.as_posix()],
            "filename":        ["b.nd2"],
            "frames":          [10],
            "image_series_id": [0],
        })

        sync_config_map(self.content_path, self.cfg_root, summary_path=summary)
        out = read_config_map(self.content_path)

        self.assertEqual(len(out), 2)
        candidate = out[out["cfg_path"].isna() | (out["cfg_path"] == "")]
        self.assertEqual(len(candidate), 1)


class TestRenameConfigFolders(TestConfigMapBase):

    def _set_cfg_folder(self, cfg_path, new_folder):
        df = read_config_map(self.content_path)
        df.loc[df["cfg_path"] == cfg_path.as_posix(), "cfg_folder"] = new_folder
        write_config_map(self.content_path, df)

    def test_rename_moves_cfg_updates_filename_and_registry(self):
        strain = self.cfg_root / "Microscope" / "Nikon (CPF)" / "NG-Sas6-KI-Sqh-mCh"
        cfg_dir = strain / "supernatant-1002"
        cfg = self._add_cfg("export_definition.cfg", "a.nd2", parent=(
            "Microscope", "Nikon (CPF)", "NG-Sas6-KI-Sqh-mCh", "supernatant-1002"),
            filename="supernatant-1002-20230726")
        (cfg_dir / "a.twoch.mp4").write_bytes(b"rendered")

        sync_config_map(self.content_path, self.cfg_root)
        self._set_cfg_folder(cfg, "supernatant-1002-v2")

        renamed = rename_config_folders(self.content_path, self.cfg_root)

        new_cfg = strain / "supernatant-1002-v2" / "export_definition.cfg"
        self.assertFalse(cfg.exists())
        self.assertTrue(new_cfg.exists())
        self.assertIn("filename = supernatant-1002-v2-20230726", new_cfg.read_text())
        row = self._row_by_cfg(renamed, new_cfg)
        self.assertEqual(row["cfg_folder"], "supernatant-1002-v2")
        # rendered media is not touched
        self.assertTrue((cfg_dir / "a.twoch.mp4").exists())

    def test_rename_works_without_any_summary(self):
        cfg = self._add_cfg("export_definition.cfg", "a.nd2", parent=("exp1",))
        sync_config_map(self.content_path, self.cfg_root, summary_path=None)
        self._set_cfg_folder(cfg, "exp1-v2")

        rename_config_folders(self.content_path, self.cfg_root)

        new_cfg = self.cfg_root / "exp1-v2" / "export_definition.cfg"
        self.assertFalse(cfg.exists())
        self.assertTrue(new_cfg.exists())

    def test_rename_works_when_media_file_is_missing(self):
        cfg = self._add_cfg("export_definition.cfg", "missing.nd2", parent=("exp1",))
        sync_config_map(self.content_path, self.cfg_root)
        self._set_cfg_folder(cfg, "exp1-v2")

        rename_config_folders(self.content_path, self.cfg_root)

        new_cfg = self.cfg_root / "exp1-v2" / "export_definition.cfg"
        self.assertTrue(new_cfg.exists())

    def test_two_cfgs_in_one_folder_rename_together(self):
        folder = self.cfg_root / "exp1"
        folder.mkdir(parents=True, exist_ok=True)
        cfg_a = folder / "export_definition.cfg"
        cfg_a.write_text(_cfg_text(Path(folder) / "a.nd2", series=0))
        cfg_b = folder / "second.cfg"
        cfg_b.write_text(_cfg_text(Path(folder) / "b.nd2", series=1))

        sync_config_map(self.content_path, self.cfg_root)
        df = read_config_map(self.content_path)
        self.assertEqual(len(df), 2)
        df["cfg_folder"] = "exp1-v2"
        write_config_map(self.content_path, df)

        renamed = rename_config_folders(self.content_path, self.cfg_root)

        for name in ("export_definition.cfg", "second.cfg"):
            new_cfg = self.cfg_root / "exp1-v2" / name
            self.assertTrue(new_cfg.exists(), new_cfg)
        self.assertFalse(cfg_a.exists())
        self.assertFalse(cfg_b.exists())
        self.assertEqual(set(renamed["cfg_folder"]), {"exp1-v2"})

    def test_unchanged_cfg_folder_does_not_move_file(self):
        cfg = self._add_cfg("export_definition.cfg", "a.nd2", parent=("exp1",))
        sync_config_map(self.content_path, self.cfg_root)

        rename_config_folders(self.content_path, self.cfg_root)

        self.assertTrue(cfg.exists())
        self.assertFalse((self.cfg_root / "exp1-v2" / "export_definition.cfg").exists())


if __name__ == '__main__':
    unittest.main()