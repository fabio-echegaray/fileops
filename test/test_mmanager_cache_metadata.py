import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from fileops.image import ImageFile
from fileops.image._cache_metadata import save_metadata_to_disk, load_metadata_from_disk, normalize_plane_keys
from fileops.image._tifffile_imagej_metadata import MetadataImageJTifffileMixin
from fileops.mixins.tiff_metadata_mixin import TiffMetadataMixinBase
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


class TestPlaneKeyPaddingConsistency(unittest.TestCase):
    """Index keys must be zero-padded with the same width at build and lookup.

    Regression for: index keys are built from the metadata-REPORTED counts
    (``_md_n_*``) but ``plane_at``/``ix_at`` used the *counted* counts
    (``n_*``).  Whenever the two differ in the number of digits (e.g. 56
    counted vs 360 reported frames), every lookup missed and Micro-Manager
    images could not be z-projected ("No index found for c=..., z=..., t=...").
    """

    def _make(self, counted, reported, nkeys=4):
        nc, nz, nt = counted
        rc, rz, rt = reported
        img = ImageFile.__new__(ImageFile)
        img.n_channels, img.n_zstacks, img.n_frames = nc, nz, nt
        img._md_n_channels, img._md_n_zstacks, img._md_n_frames = rc, rz, rt
        wc, wz, wt = len(str(rc)), len(str(rz)), len(str(rt))
        img.all_planes_md_dict = {
            f"c{c:0{wc}d}z{z:0{wz}d}t{t:0{wt}d}": c * 100 + z * 10 + t
            for t in range(nkeys) for z in range(nz) for c in range(nc)
        }
        img.log = MagicMock()
        return img

    def test_mismatched_frame_width_still_looks_up(self):
        # reported frames=360 (3 digits) vs counted frames=56 (2 digits)
        img = self._make(counted=(2, 25, 56), reported=(2, 25, 360))
        self.assertEqual(img.plane_at(0, 0, 0), "c0z00t000")
        self.assertEqual(img.plane_at(0, 24, 0), "c0z24t000")
        self.assertEqual(img.plane_at(1, 0, 2), "c1z00t002")
        self.assertEqual(img.ix_at(0, 0, 0), 0)
        self.assertEqual(img.ix_at(0, 24, 0), 240)
        self.assertEqual(img.ix_at(1, 0, 2), 102)

    def test_mismatched_z_width_still_looks_up(self):
        # reported slices=30 (2 digits) vs counted slices=9 (1 digit)
        img = self._make(counted=(2, 9, 3), reported=(2, 30, 3))
        self.assertEqual(img.plane_at(0, 8, 0), "c0z08t0")
        self.assertEqual(img.ix_at(0, 8, 0), 80)
        self.assertEqual(img.ix_at(1, 8, 2), 182)

    def test_cached_dictionary_uses_same_padding(self):
        # after a cache round-trip the restored _md counts keep lookups working
        img = self._make(counted=(2, 25, 56), reported=(2, 25, 360))
        for ix in (0, 1, 240, 102):
            img.ix_at(ix // 100, (ix // 10) % 10, ix % 10)
            self.assertIn(ix, img.all_planes_md_dict.values())

    def test_fallback_when_md_counts_missing(self):
        img = ImageFile.__new__(ImageFile)
        img.n_channels, img.n_zstacks, img.n_frames = 2, 5, 3
        img.log = MagicMock()
        self.assertEqual(img.plane_at(0, 0, 0), "c0z0t0")

    def test_negative_reported_counts_fall_back_to_counted(self):
        # OME-derived TIFFs with no <Plane> info report -1 for every axis;
        # _pad_width must fall back to the counted sizes (1/1/1 in the
        # optimised max-projection case).
        img = ImageFile.__new__(ImageFile)
        img.n_channels, img.n_zstacks, img.n_frames = 1, 1, 1
        img._md_n_channels = img._md_n_zstacks = img._md_n_frames = -1
        img.log = MagicMock()
        self.assertEqual(img._pad_width(-1, 1), 1)
        self.assertEqual(img.plane_at(0, 0, 0), "c0z0t0")

    def _make_negative_reported_cache_like(self):
        # simulate the broken state produced by older builders: keys
        # zero-padded with len(str(-1)) == 2, counted sizes = 1/1/1
        img = ImageFile.__new__(ImageFile)
        img.n_channels, img.n_zstacks, img.n_frames = 1, 1, 1
        img._md_n_channels = img._md_n_zstacks = img._md_n_frames = -1
        img.all_planes_md_dict = {"c00z00t00": 0}
        img.log = MagicMock()
        return img

    def test_normalize_plane_keys_fixes_negative_width(self):
        img = self._make_negative_reported_cache_like()
        normalize_plane_keys(img)
        self.assertEqual(img.all_planes_md_dict, {"c0z0t0": 0})
        self.assertEqual(img.all_planes, ["c0z0t0"])
        self.assertEqual(img.plane_at(0, 0, 0), "c0z0t0")
        self.assertEqual(img.ix_at(0, 0, 0), 0)

    def test_normalize_plane_keys_preserves_values_and_order(self):
        # counted 1/1/1 reported -1, values must survive the rewrite untouched
        img = ImageFile.__new__(ImageFile)
        img.n_channels, img.n_zstacks, img.n_frames = 1, 1, 1
        img._md_n_channels = img._md_n_zstacks = img._md_n_frames = -1
        img.all_planes_md_dict = {"c00z00t00": 3, "c00z01t00": 7}
        img.log = MagicMock()
        normalize_plane_keys(img)
        self.assertEqual(img.all_planes_md_dict, {"c0z0t0": 3, "c0z1t0": 7})
        self.assertEqual(img.all_planes, ["c0z0t0", "c0z1t0"])


class TestInitMetadataRunsOnce(unittest.TestCase):
    """TiffMetadataMixinBase._init_metadata must only act on its first call.

    TifffileOMEImageFile.__init__ walks the diamond init chain several
    times; ImageFile.__init__ ends with ``super().__init__()`` which
    re-enters the metadata mixin. Without the guard, the cache-hit path
    restored the stale tifffile/ImageJ-fallback counts (1/1/1) on top of
    the OME-derived counts (181 t x 2 c) — the loader reported the wrong
    dimensions. Regression for FileOps TODO #41(d).
    """

    def _make(self):
        obj = TiffMetadataMixinBase.__new__(TiffMetadataMixinBase)
        obj.error_loading_metadata = False
        obj.image_path = Path("test.tif")
        obj.log = MagicMock()
        return obj

    def test_second_call_is_a_no_op_and_keeps_current_state(self):
        obj = self._make()
        obj.n_frames = 181  # state set by OMEImageFile._load_imageseries afterwards
        with patch("fileops.mixins.tiff_metadata_mixin.load_metadata_from_disk",
                   return_value=True) as ld, \
                patch("fileops.mixins.tiff_metadata_mixin.tf.TiffFile"), \
                patch("fileops.mixins.tiff_metadata_mixin.normalize_plane_keys"):
            obj._init_metadata()   # would normally restore the stale cache here
            obj._init_metadata()   # must be a no-op
        self.assertEqual(ld.call_count, 1)
        self.assertEqual(obj.n_frames, 181)


if __name__ == '__main__':
    unittest.main()
