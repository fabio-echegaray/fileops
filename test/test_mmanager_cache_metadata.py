import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from fileops.image._cache_metadata import save_metadata_to_disk, load_metadata_from_disk
from fileops.image._mmanager_metadata import MetadataVersion10Mixin


def _make_mm_tiff_file():
    """Return a mock Micro-Manager TIFF file as read by tifffile.

    Micro-Manager stores acquisition metadata *inside* the TIFF under
    ``micromanager_metadata``.  ``_load_metadata`` reads two parts of it:

    * ``Summary`` – acquisition-wide settings (pixel type, dimensions,
      z-step, frame interval, stage positions).
    * ``IndexMap`` – per-frame position label.

    Everything else on the tiff object (``imagej_metadata``, keyframe
    shape/axes) is standard tifffile, not Micro-Manager-specific.
    """
    # --- standard tifffile keyframe (not Micro-Manager-specific) ---
    keyframe = MagicMock()
    keyframe.shape = (64, 64)
    keyframe.axes = "YX"
    keyframe.imagewidth = 64
    keyframe.imagelength = 64

    # --- Micro-Manager metadata embedded in the TIFF ---
    mm_summary = {
        "PixelType":      "uint16",
        "Width":          64,
        "Height":         64,
        "Slices":         1,
        "Frames":         3,
        "Channels":       2,
        "Positions":      1,
        "z-step_um":      1.0,
        "Interval_ms":    1000,
        "StagePositions": ["pos0"],
    }
    mm_index_map = {"Position": ["pos0"]}
    mm_metadata = {"Summary": mm_summary, "IndexMap": mm_index_map}

    # --- assemble the tiff object ---
    tif = MagicMock()
    tif.imagej_metadata = None              # standard tifffile attribute
    tif.micromanager_metadata = mm_metadata  # Micro-Manager-specific
    tif.pages.keyframe = keyframe            # standard tifffile attribute

    return tif


def _make_mm_mixin(tmp_path):
    """Create a MetadataVersion10Mixin bypassing __init__ for testing.

    Only ImageFileBase attributes that ``_load_metadata`` reads/writes
    before the metadata file check are initialised here.  Everything
    else is populated by ``_load_metadata`` itself.
    """
    obj = MetadataVersion10Mixin.__new__(MetadataVersion10Mixin)

    # paths (ImageFileBase)
    obj.image_path = tmp_path / "test.tif"
    obj.metadata_path = None  # missing → triggers error_loading_metadata = True

    # mutable containers that _load_metadata appends to
    obj.frames = []
    obj.timestamps = []
    obj.channels = set()
    obj.zstacks = []
    obj.zstacks_um = []
    obj.files = []
    obj.all_planes = []
    obj.all_planes_md_dict = {}
    obj.frames_per_file = {}

    obj.log = MagicMock()
    return obj


class TestBug15MdFrames(unittest.TestCase):

    def setUp(self):
        self._tmpdir = Path(tempfile.mkdtemp())

    @patch("fileops.image._mmanager_metadata.tf.TiffFile")
    def test_md_frames_set_when_metadata_missing(self, mock_tffile):
        """_md_frames and _md_timestamps must be set when no metadata file exists."""
        mock_tffile.return_value.__enter__ = MagicMock(return_value=_make_mm_tiff_file())
        mock_tffile.return_value.__exit__ = MagicMock(return_value=False)

        mixin = _make_mm_mixin(self._tmpdir)
        mixin._load_metadata()

        self.assertTrue(mixin.error_loading_metadata)
        self.assertTrue(hasattr(mixin, "_md_frames"))
        self.assertTrue(hasattr(mixin, "_md_timestamps"))
        self.assertEqual(mixin._md_frames, [0, 1, 2])
        self.assertEqual(len(mixin._md_timestamps), 3)

    @patch("fileops.image._mmanager_metadata.tf.TiffFile")
    def test_save_metadata_succeeds_with_error_metadata(self, mock_tffile):
        """save_metadata_to_disk must not crash when error_loading_metadata is True."""
        mock_tffile.return_value.__enter__ = MagicMock(return_value=_make_mm_tiff_file())
        mock_tffile.return_value.__exit__ = MagicMock(return_value=False)

        mixin = _make_mm_mixin(self._tmpdir)
        mixin._load_metadata()

        mixin.image_path = self._tmpdir / "test.tif"
        save_metadata_to_disk(mixin)

        md_path = self._tmpdir / "test.tif.fileops.metadata.safe_to_delete.txt.gz"
        self.assertTrue(md_path.exists())

    @patch("fileops.image._mmanager_metadata.tf.TiffFile")
    def test_save_load_roundtrip_with_error_metadata(self, mock_tffile):
        """save then load must restore _md_frames and _md_timestamps."""
        mock_tffile.return_value.__enter__ = MagicMock(return_value=_make_mm_tiff_file())
        mock_tffile.return_value.__exit__ = MagicMock(return_value=False)

        mixin = _make_mm_mixin(self._tmpdir)
        mixin._load_metadata()
        mixin.image_path = self._tmpdir / "test.tif"

        save_metadata_to_disk(mixin)

        mixin2 = _make_mm_mixin(self._tmpdir)
        mixin2.image_path = self._tmpdir / "test.tif"
        result = load_metadata_from_disk(mixin2)
        self.assertTrue(result)
        self.assertEqual(mixin2._md_frames, [0, 1, 2])
        self.assertEqual(len(mixin2._md_timestamps), 3)


if __name__ == '__main__':
    unittest.main()
