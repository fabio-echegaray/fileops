import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fileops.export.config_data_section import read_data_section


class _StubImage:
    """Minimal stand-in for an ImageFile opened by read_data_section."""
    frames = list(range(5))
    channels = [0, 1]
    zstacks = [0, 1]
    series = 0

    def add_processor(self, *args, **kwargs):
        pass


def _write_media(root: Path, rel: str) -> Path:
    media = root / rel
    media.parent.mkdir(parents=True, exist_ok=True)
    media.write_bytes(b"stub")
    return media


class TestMediaPathResolution(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.root = self.tmp / "media_root"
        self.cfg_dir = self.tmp / "configs"
        self.cfg_dir.mkdir(parents=True)
        self.cfg_path = self.cfg_dir / "movie.cfg"

    def _write_cfg(self, image_value: str):
        self.cfg_path.write_text(f"[DATA]\nimage = {image_value}\n")

    def _read_captured_path(self):
        captured = {}

        def _fake_load(img_path, **kwargs):
            captured["path"] = Path(img_path)
            return _StubImage()

        with patch("fileops.export.config_data_section.load_image_file", side_effect=_fake_load):
            read_data_section(self.cfg_path, with_root_path=self.root)
        return captured["path"]

    def test_relative_path_resolves_against_root(self):
        media = _write_media(self.root, "Nikon (CPF)/20240302/CHX_500ug_1/data.ome.tif")
        self._write_cfg("Nikon (CPF)/20240302/CHX_500ug_1/data.ome.tif")
        self.assertEqual(self._read_captured_path(), media)

    def test_relative_path_without_root_resolves_against_config_folder(self):
        media = _write_media(self.cfg_dir, "data.ome.tif")
        self._write_cfg("data.ome.tif")

        captured = {}
        with patch("fileops.export.config_data_section.load_image_file",
                   side_effect=lambda img_path, **kw: captured.update(path=Path(img_path)) or _StubImage()):
            read_data_section(self.cfg_path)
        self.assertEqual(captured["path"], media)

    def test_existing_absolute_path_is_kept_unchanged(self):
        media = _write_media(self.root, "Nikon (CPF)/20240302/CHX_500ug_1/data.ome.tif")
        self._write_cfg(str(media))
        self.assertEqual(self._read_captured_path(), media)

    def test_stale_absolute_path_is_reanchored_under_root(self):
        media = _write_media(self.root, "Nikon (CPF)/20240302/CHX_500ug_1/data.ome.tif")
        self._write_cfg(f"/Volumes/T7/Microscope/Nikon (CPF)/20240302/CHX_500ug_1/data.ome.tif")
        self.assertEqual(self._read_captured_path(), media)

    def test_stale_absolute_path_keeps_deepest_matching_tail(self):
        _write_media(self.root, "Nikon (CPF)/20240302/CHX_500ug_1/data.ome.tif")
        _write_media(self.root, "CHX_500ug_2/data.ome.tif")
        self._write_cfg(f"/Volumes/T7/Microscope/Nikon (CPF)/20240302/CHX_500ug_1/data.ome.tif")
        self.assertEqual(
            self._read_captured_path(),
            self.root / "Nikon (CPF)/20240302/CHX_500ug_1/data.ome.tif",
        )

    def test_stale_absolute_path_without_root_raises(self):
        self._write_cfg("/Volumes/T7/Microscope/Nikon (CPF)/20240302/CHX_500ug_1/data.ome.tif")
        with self.assertRaises(FileNotFoundError):
            read_data_section(self.cfg_path)

    def test_stale_absolute_path_with_root_but_no_match_raises(self):
        self._write_cfg("/Volumes/T7/Microscope/Nikon (CPF)/20240302/CHX_500ug_1/missing.ome.tif")
        with self.assertRaises(FileNotFoundError):
            read_data_section(self.cfg_path, with_root_path=self.root)

    def test_relative_path_missing_raises(self):
        self._write_cfg("Nikon (CPF)/20240302/CHX_500ug_1/missing.ome.tif")
        with self.assertRaises(FileNotFoundError):
            read_data_section(self.cfg_path, with_root_path=self.root)


if __name__ == '__main__':
    unittest.main()