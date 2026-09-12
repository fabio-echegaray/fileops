from pathlib import Path
import tempfile
import unittest

from fileops.export.config import search_config_files


class TestConfigDiscovery(unittest.TestCase):
    def test_appledouble_cfg_files_are_ignored(self):
        with tempfile.TemporaryDirectory() as directory:
            config_dir = Path(directory)
            (config_dir / "export_definition.cfg").write_text("[DATA]\n")
            (config_dir / "._export_definition.cfg").write_bytes(b"appledouble")

            config_files = search_config_files(config_dir)

            self.assertEqual(config_files, [config_dir / "export_definition.cfg"])