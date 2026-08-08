import unittest
import tempfile
from pathlib import Path

from fileops.image.factory import load_image_file


class TestLoadImageFile(unittest.TestCase):

    def test_nonexistent_path_raises(self):
        with self.assertRaises(FileNotFoundError):
            load_image_file(Path("/nonexistent/path/file.tif"))

    def test_hidden_file_returns_none(self):
        tmpdir = tempfile.mkdtemp()
        hidden = Path(tmpdir) / ".hidden.tif"
        hidden.touch()
        result = load_image_file(hidden)
        self.assertIsNone(result)

    def test_unsupported_extension_returns_none(self):
        tmpdir = tempfile.mkdtemp()
        unsupported = Path(tmpdir) / "data.xyz"
        unsupported.touch()
        result = load_image_file(unsupported)
        self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main()
