import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fileops.export.config_data_section import read_data_section
from fileops.image.ops.rescale_proc import RescaleProcessor


class _RecorderImage:
    """Stub ImageFile that records the processors added to it."""
    frames = list(range(5))
    channels = [0, 1]
    zstacks = [0, 1]
    series = 0

    def __init__(self, *args, **kwargs):
        self.processors = []

    def add_processor(self, processor):
        self.processors.append(processor)


def _write(tmpdir: Path, text: str) -> Path:
    (tmpdir / "data.tif").write_bytes(b"stub")
    cfg = tmpdir / "movie.cfg"
    cfg.write_text(text)
    return cfg


class TestRescaleOpDetection(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def _read(self, cfg_text: str):
        img = _RecorderImage()
        with patch("fileops.export.config_data_section.load_image_file", return_value=img):
            read_data_section(_write(self.tmp, cfg_text))
        return img

    def test_rescale_yes_enables_processor(self):
        img = self._read("[DATA]\nimage = data.tif\nrescale = yes\n")
        self.assertIsInstance(img.processors[0], RescaleProcessor)

    def test_rescale_no_disables_processor(self):
        img = self._read("[DATA]\nimage = data.tif\nrescale = no\n")
        self.assertEqual(len(img.processors), 0)

    def test_rescale_no_not_overridden_by_channel_params(self):
        # regression: `rescale = no` in the DATA header must win over
        # rescale_min/rescale_max found in CHANNEL sections.
        img = self._read(
            "[DATA]\nimage = data.tif\nrescale = no\n\n"
            "[CHANNEL-1]\nname = ch1\nrescale_min = 5500\nrescale_max = 16000\n"
        )
        self.assertEqual(len(img.processors), 0)

    def test_channel_rescale_params_enable_processor(self):
        # rescale params can live in CHANNEL sections (not only DATA).
        img = self._read(
            "[DATA]\nimage = data.tif\n\n"
            "[CHANNEL-1]\nname = ch1\nrescale_min = 5500\nrescale_max = 16000\n"
        )
        self.assertIsInstance(img.processors[0], RescaleProcessor)

    def test_data_rescale_min_max_enable_processor(self):
        img = self._read(
            "[DATA]\nimage = data.tif\nrescale_min = 5500\nrescale_max = 16000\n"
        )
        self.assertIsInstance(img.processors[0], RescaleProcessor)


if __name__ == '__main__':
    unittest.main()