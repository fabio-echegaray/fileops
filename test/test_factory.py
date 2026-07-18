import pytest
from pathlib import Path
from unittest.mock import patch

from fileops.image.factory import load_image_file


class TestLoadImageFile:
    def test_nonexistent_path_raises(self):
        with pytest.raises(FileNotFoundError):
            load_image_file(Path("/nonexistent/path/file.tif"))

    def test_hidden_file_returns_none(self, tmp_path):
        hidden = tmp_path / ".hidden.tif"
        hidden.touch()
        result = load_image_file(hidden)
        assert result is None

    def test_unsupported_extension_returns_none(self, tmp_path):
        unsupported = tmp_path / "data.xyz"
        unsupported.touch()
        result = load_image_file(unsupported)
        assert result is None
