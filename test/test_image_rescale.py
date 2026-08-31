import unittest
import numpy as np

from fileops.image.ops._image_rescale import rescale


class TestImageRescale(unittest.TestCase):

    def setUp(self):
        self.img_uint16 = np.array([[0, 32768], [65535, 16384]], dtype=np.uint16)
        self.img_float32 = np.array([[0.0, 0.5], [1.0, 0.25]], dtype=np.float32)

    def test_no_rescale_no_gamma_returns_float(self):
        result = rescale(self.img_uint16, {})
        self.assertEqual(result.dtype, np.float64)

    def test_rescale_bool_enables_percentile_rescale(self):
        result = rescale(self.img_uint16, {'rescale': True})
        self.assertLessEqual(result.max(), 1.0)
        self.assertGreaterEqual(result.min(), 0.0)

    def test_rescale_with_min_max(self):
        result = rescale(self.img_uint16, {'rescale': True, 'rescale_min': 0, 'rescale_max': 65535})
        self.assertLessEqual(result.max(), 1.0)

    def test_rescale_dict_range(self):
        result = rescale(self.img_uint16, {'rescale': {'range': (0, 65535)}})
        self.assertLessEqual(result.max(), 1.0)

    def test_gamma_adjustment(self):
        result = rescale(self.img_float32, {'gamma_value': 0.5, 'gamma_gain': 1.0})
        self.assertTrue(np.issubdtype(result.dtype, np.floating))
        self.assertLessEqual(result.max(), 1.0)

    def test_rescale_and_gamma_raises(self):
        with self.assertRaises(ValueError):
            rescale(self.img_uint16, {'rescale': True, 'gamma_value': 0.5, 'gamma_gain': 1.0})

    def test_as_original_dtype_uint16(self):
        result = rescale(self.img_uint16, {'rescale': True}, as_original_dtype=True)
        self.assertEqual(result.dtype, np.uint16)

    def test_as_original_dtype_float32(self):
        result = rescale(self.img_float32, {}, as_original_dtype=True)
        self.assertEqual(result.dtype, np.float32)

    def test_does_not_modify_original(self):
        original = self.img_uint16.copy()
        rescale(self.img_uint16, {'rescale': True})
        np.testing.assert_array_equal(self.img_uint16, original)

    def test_rescale_min_max_with_none_values_raises(self):
        with self.assertRaises(TypeError):
            rescale(self.img_uint16, {'rescale': True, 'rescale_min': None, 'rescale_max': None})


if __name__ == '__main__':
    unittest.main()
