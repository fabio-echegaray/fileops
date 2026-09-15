import unittest
import unittest.mock
from types import SimpleNamespace

import numpy as np

from fileops.image.exceptions import FrameNotFoundError
from fileops.image.ops import ZProjection, zprojection_from_str, depth_field, z_volume


class TestZProjectionFromStr(unittest.TestCase):

    def test_depth_is_not_a_projection_type(self):
        # depth-coding is a rendering (colormap) concern, not a reducer over
        # z-planes, so it has no enum member and stays UNSPECIFIED here
        self.assertEqual(zprojection_from_str('depth'), ZProjection.UNSPECIFIED)
        self.assertEqual(zprojection_from_str('all-depth'), ZProjection.UNSPECIFIED)
        self.assertEqual(zprojection_from_str('code'), ZProjection.UNSPECIFIED)

    def test_unknown_string(self):
        self.assertEqual(zprojection_from_str('weird'), ZProjection.UNSPECIFIED)

    def test_non_string(self):
        self.assertIsNone(zprojection_from_str(ZProjection.MAX))

    def test_normal_projection(self):
        self.assertEqual(zprojection_from_str('all-max'), ZProjection.MAX)
        self.assertEqual(zprojection_from_str('mean'), ZProjection.MEAN)
        self.assertEqual(zprojection_from_str('median'), ZProjection.MEDIAN)


class _PlaneFileStub:
    """Stub exposing the plane-reading API that _read_planes relies on."""

    def __init__(self, n=4, height=4, width=5):
        self.n_zstacks = n
        self.planes = [np.full((height, width), i, dtype=np.uint16) for i in range(n)]
        self.log = unittest.mock.MagicMock()

    def ix_at(self, channel, z, frame):
        return z

    def plane_at(self, channel, z, frame):
        return z

    def _image(self, ix):
        return SimpleNamespace(image=self.planes[ix])


class TestZVolume(unittest.TestCase):

    def test_returns_volume_of_all_planes(self):
        out = z_volume(_PlaneFileStub(), frame=0, channel=0)
        self.assertEqual(out.shape, (4, 4, 5))
        np.testing.assert_array_equal(out[2], 2)

    def test_z_subset(self):
        out = z_volume(_PlaneFileStub(), frame=0, channel=0, z_subset=[1, 3])
        self.assertEqual(out.shape, (2, 4, 5))
        np.testing.assert_array_equal(out[0], 1)
        np.testing.assert_array_equal(out[1], 3)

    def test_dtype_preserved(self):
        out = z_volume(_PlaneFileStub(), frame=0, channel=0)
        self.assertEqual(out.dtype, np.uint16)

    def test_empty_subset_raises(self):
        with self.assertRaises(FrameNotFoundError):
            z_volume(_PlaneFileStub(), frame=0, channel=0, z_subset=[])

    def test_output_feeds_depth_field(self):
        vol = z_volume(_PlaneFileStub(), frame=0, channel=0)
        # all pixels are brightest at the top plane (index n-1)
        field = depth_field(vol)
        np.testing.assert_array_equal(field, np.ones((4, 5)))


class TestDepthField(unittest.TestCase):

    def setUp(self):
        # 4 slices progressively shifted toward the bottom-right corner
        vol = np.zeros((4, 8, 8), dtype=np.float64)
        for k in range(4):
            vol[k, k, k] = 1.0 + k
        self.vol = vol

    def test_returns_2d_field(self):
        out = depth_field(self.vol)
        self.assertEqual(out.shape, (8, 8))
        self.assertEqual(out.ndim, 2)

    def test_dtype_is_float(self):
        out = depth_field(self.vol)
        self.assertTrue(np.issubdtype(out.dtype, np.floating))

    def test_values_in_unit_range(self):
        out = depth_field(self.vol)
        self.assertGreaterEqual(out.min(), 0.0)
        self.assertLessEqual(out.max(), 1.0)

    def test_encodes_argmax_z(self):
        out = depth_field(self.vol)
        # pixel (0, 0) peaks at z=0 (bottom), pixel (3, 3) peaks at z=3 (top)
        self.assertEqual(out[0, 0], 0.0)
        self.assertEqual(out[3, 3], 1.0)

    def test_flat_volume_points_bottom(self):
        flat = np.ones((4, 5, 5))
        out = depth_field(flat)
        np.testing.assert_array_equal(out, np.zeros((5, 5)))

    def test_single_slice(self):
        vol = np.random.rand(1, 6, 6)
        out = depth_field(vol)
        np.testing.assert_array_equal(out, np.zeros((6, 6)))


if __name__ == '__main__':
    unittest.main()