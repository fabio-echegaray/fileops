import configparser
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fileops.export.config import read_config_projections


class TestReadConfigProjections(unittest.TestCase):

    def setUp(self):
        self.cfg = configparser.ConfigParser()
        self.img_file = SimpleNamespace(series=0, n_zstacks=30)
        self.povr = SimpleNamespace(frames=[0, 1], channels=[0], zstacks=[0, 1, 2])

    def _read(self, text):
        cfg = configparser.ConfigParser()
        cfg.read_string(text)
        with patch("fileops.export.config.process_overrides_of_section", return_value=self.povr), \
             patch("fileops.export.config.update_channel_config_with_section_overrides",
                   side_effect=lambda povr, section: povr):
            return read_config_projections(Path("/fake/x.cfg"), cfg, self.img_file, self.povr, None)

    def test_zstacks_is_populated(self):
        prjs = self._read("[PROJECTION-1]\nzstack = 0..2\nfilename = out\n")
        self.assertEqual(len(prjs), 1)
        self.assertEqual(prjs[0].zstacks, [0, 1, 2])

    def test_zstack_fn_and_filename_defaults(self):
        prjs = self._read("[PROJECTION-1]\n")
        self.assertEqual(prjs[0].zstack_fn, "all-max")
        self.assertEqual(prjs[0].filename, "no_filename_given")

    def test_bleach_correction_parsing(self):
        prjs = self._read("[PROJECTION-1]\nbleach_correction = yes\n")
        self.assertTrue(prjs[0].bleach_correction)
        prjs_no = self._read("[PROJECTION-1]\nbleach_correction = no\n")
        self.assertFalse(prjs_no[0].bleach_correction)


if __name__ == '__main__':
    unittest.main()