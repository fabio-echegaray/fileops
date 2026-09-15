import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fileops.export.config_data_section import read_data_section, parse_pixel_size


class _StubImage:
    """Minimal stand-in for an ImageFile opened by read_data_section."""
    frames = list(range(5))
    channels = [0, 1]
    zstacks = [0, 1]
    series = 0
    um_per_pix = 1.0
    pix_per_um = 1.0

    def add_processor(self, *args, **kwargs):
        pass


class TestParsePixelSize(unittest.TestCase):

    def test_bare_number_means_um(self):
        self.assertEqual(parse_pixel_size("0.107"), 0.107)

    def test_um_unit(self):
        self.assertEqual(parse_pixel_size("0.107 um"), 0.107)
        self.assertEqual(parse_pixel_size("0.107 µm"), 0.107)

    def test_nm_unit_converts_to_um(self):
        self.assertEqual(parse_pixel_size("107 nm"), 0.107)

    def test_mm_unit_converts_to_um(self):
        self.assertEqual(parse_pixel_size("1.07e-4 mm"), 0.107)

    def test_m_unit_converts_to_um(self):
        self.assertAlmostEqual(parse_pixel_size("1.07e-7 m"), 0.107)

    def test_invalid_specs(self):
        for bad in ["", "abc", "-5", "0", "0 nm", "107 furlongs", None, 0.107]:
            self.assertIsNone(parse_pixel_size(bad))


class TestPixelSizeOverride(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.cfg_dir = self.tmp / "configs"
        self.cfg_dir.mkdir(parents=True)
        self.cfg_path = self.cfg_dir / "movie.cfg"
        media = self.tmp / "data.ome.tif"
        media.write_bytes(b"stub")
        self.media = media

    def _read(self):
        with patch("fileops.export.config_data_section.load_image_file",
                   return_value=_StubImage()):
            cfg, img_file, _param, _roi = read_data_section(self.cfg_path)
        return img_file

    def test_override_applies_nm(self):
        self.cfg_path.write_text(f"[DATA]\nimage = {self.media}\npixel_size = 65 nm\n")
        img_file = self._read()
        self.assertAlmostEqual(img_file.um_per_pix, 0.065)
        self.assertAlmostEqual(img_file.pix_per_um, 1.0 / 0.065)

    def test_override_applies_um(self):
        self.cfg_path.write_text(f"[DATA]\nimage = {self.media}\npixel_size = 0.107 um\n")
        img_file = self._read()
        self.assertAlmostEqual(img_file.pix_per_um, 1.0 / 0.107)

    def test_missing_override_keeps_file_value(self):
        self.cfg_path.write_text(f"[DATA]\nimage = {self.media}\n")
        self.assertEqual(self._read().um_per_pix, 1.0)

    def test_invalid_override_keeps_file_value(self):
        self.cfg_path.write_text(f"[DATA]\nimage = {self.media}\npixel_size = banana\n")
        img_file = self._read()
        self.assertEqual(img_file.um_per_pix, 1.0)


if __name__ == '__main__':
    unittest.main()