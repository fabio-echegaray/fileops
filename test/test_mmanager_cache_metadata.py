import unittest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

from fileops.image._mmanager_metadata import MetadataVersion10Mixin
from fileops.image._cache_metadata import save_metadata_to_disk, load_metadata_from_disk


def _make_mixin(error_loading=True):
    """Build a MetadataVersion10Mixin-shaped object for testing cache routines."""
    obj = MagicMock()

    # core attributes that save_metadata_to_disk always reads
    obj.pix_per_um = 1.0
    obj.um_per_pix = 1.0
    obj.um_per_z = 1.0
    obj.width = 512
    obj.height = 512
    obj.n_frames = 3
    obj.n_channels = 2
    obj.n_zstacks = 5
    obj.n_positions = 1
    obj.frames = [0, 1, 2]
    obj.timestamps = [0.0, 1.0, 2.0]
    obj.channels = {0, 1}
    obj.zstacks = [0, 1, 2, 3, 4]
    obj.zstacks_um = [0.0, 1.0, 2.0, 3.0, 4.0]
    obj.positions = {"pos0"}
    obj.all_planes_md_dict = {}
    obj.time_interval = 1.0
    obj.all_series = set()
    obj.files = ["file1.tif", "file2.tif"]
    obj.frames_per_file = {"file1.tif": 100, "file2.tif": 100}
    obj._md_n_positions = 1
    obj._md_n_zstacks = 5
    obj._md_n_frames = 3
    obj._md_n_channels = 2
    obj._md_timestamps = [0.0, 1.0, 2.0]
    obj._md_zstacks = [0, 1, 2, 3, 4]
    obj._counted_frames = 3
    obj._counted_channels = 2
    obj._counted_zstacks = 5
    obj._md_dt = 1.0
    obj._dtype = "uint16"
    obj.log = MagicMock()

    if error_loading:
        # Simulate the bug: _md_frames is never set
        del obj._md_frames
    else:
        obj._md_frames = [0, 1, 2]

    return obj


class TestCacheMetadataMissingFrames(unittest.TestCase):

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        self._tmp = Path(self._tmpdir)

    def test_save_metadata_crashes_without_md_frames(self):
        """save_metadata_to_disk must not crash when _md_frames is missing (bug #15)."""
        imf = _make_mixin(error_loading=True)
        imf.image_path = self._tmp / "test.tif"

        save_metadata_to_disk(imf)

        md_path = self._tmp / "test.tif.fileops.metadata.safe_to_delete.txt.gz"
        self.assertTrue(md_path.exists())

    def test_save_metadata_succeeds_with_md_frames(self):
        """save_metadata_to_disk should succeed when _md_frames is present."""
        imf = _make_mixin(error_loading=False)
        imf.image_path = self._tmp / "test.tif"

        save_metadata_to_disk(imf)

        md_path = self._tmp / "test.tif.fileops.metadata.safe_to_delete.txt.gz"
        self.assertTrue(md_path.exists())

    def test_load_metadata_roundtrip(self):
        """save then load should restore all attributes."""
        imf = _make_mixin(error_loading=False)
        imf.image_path = self._tmp / "test.tif"

        save_metadata_to_disk(imf)

        imf2 = _make_mixin(error_loading=True)
        imf2.image_path = self._tmp / "test.tif"

        result = load_metadata_from_disk(imf2)
        self.assertTrue(result)
        self.assertEqual(imf2._md_frames, [0, 1, 2])
        self.assertEqual(imf2._md_timestamps, [0.0, 1.0, 2.0])

    def test_md_frames_set_when_metadata_missing(self):
        """_md_frames must exist after _load_metadata with no metadata file (bug #15)."""
        mixin = MetadataVersion10Mixin.__new__(MetadataVersion10Mixin)

        # Simulate the attributes that _load_metadata sets before the branch
        mixin.image_path = Path("/fake/test.tif")
        mixin.frames = [0, 1, 2]
        mixin.timestamps = [0.0, 1.0, 2.0]
        mixin.error_loading_metadata = True
        mixin._md_n_frames = 3
        mixin._md_n_channels = 2
        mixin._md_n_zstacks = 5
        mixin._md_dt = 1.0
        mixin.frames_per_file = {}
        mixin.files = []
        mixin.channels = set()
        mixin.zstacks = []
        mixin.zstacks_um = []
        mixin.all_planes = []
        mixin.all_planes_md_dict = {}
        mixin.log = MagicMock()

        self.assertTrue(hasattr(mixin, "_md_frames"))
        self.assertEqual(mixin._md_frames, [0, 1, 2])
        self.assertEqual(mixin._md_timestamps, [0.0, 1.0, 2.0])


if __name__ == '__main__':
    unittest.main()
