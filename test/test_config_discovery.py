from pathlib import Path
import tempfile
import unittest

from fileops.export.config import build_config_list, search_config_files


class TestConfigDiscovery(unittest.TestCase):
    def test_appledouble_cfg_files_are_ignored(self):
        with tempfile.TemporaryDirectory() as directory:
            config_dir = Path(directory)
            (config_dir / "export_definition.cfg").write_text("[DATA]\n")
            (config_dir / "._export_definition.cfg").write_bytes(b"appledouble")

            config_files = search_config_files(config_dir)

            self.assertEqual(config_files, [config_dir / "export_definition.cfg"])

    def test_hidden_directories_are_not_scanned(self):
        with tempfile.TemporaryDirectory() as directory:
            config_dir = Path(directory)
            (config_dir / "export_definition.cfg").write_text("[DATA]\n")
            hidden = config_dir / ".venv" / "lib"
            hidden.mkdir(parents=True)
            (hidden / "_c_ast.cfg").write_text("ArrayDecl: [type*, dim*, dim_quals]\n")

            config_files = search_config_files(config_dir)

            self.assertEqual(config_files, [config_dir / "export_definition.cfg"])

    def test_non_config_cfg_files_are_skipped(self):
        with tempfile.TemporaryDirectory() as directory:
            config_dir = Path(directory)
            (config_dir / "_c_ast.cfg").write_text("ArrayDecl: [type*, dim*, dim_quals]\n")
            img = config_dir / "img.nd2"
            img.touch()
            (config_dir / "export_definition.cfg").write_text(
                f"[DATA]\nimage = {img.as_posix()}\n")

            df = build_config_list(config_dir)

            self.assertEqual(len(df), 1)
            self.assertEqual(Path(df.loc[0, "cfg_path"]).name, "export_definition.cfg")
