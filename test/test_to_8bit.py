import unittest
import numpy as np

from fileops.image.to_8bit import to_8bit


class TestTo8Bit(unittest.TestCase):

    def setUp(self):
        self.img_uint8 = np.array([[0, 128], [255, 64]], dtype=np.uint8)
        self.img_uint16 = np.array([[0, 32768], [65535, 16384]], dtype=np.uint16)
        self.img_float32 = np.array([[0.0, 0.5], [1.0, 0.25]], dtype=np.float32)
        self.img_zeros = np.zeros((4, 4), dtype=np.uint16)

    def test_uint8_passthrough(self):
        result = to_8bit(self.img_uint8)
        self.assertEqual(result.dtype, np.uint8)
        self.assertEqual(result.shape, self.img_uint8.shape)

    def test_uint16_scaled(self):
        result = to_8bit(self.img_uint16)
        self.assertEqual(result.dtype, np.uint8)
        self.assertEqual(result.max(), 255)

    def test_float32_scaled(self):
        result = to_8bit(self.img_float32)
        self.assertEqual(result.dtype, np.uint8)
        self.assertEqual(result.max(), 255)

    def test_zeros_returns_zeros(self):
        result = to_8bit(self.img_zeros)
        self.assertEqual(result.dtype, np.uint8)
        self.assertEqual(result.sum(), 0)

    def test_all_same_value(self):
        img = np.full((3, 3), 42, dtype=np.uint16)
        result = to_8bit(img)
        self.assertEqual(result.dtype, np.uint8)
        self.assertEqual(result.sum(), 0)

    def test_single_pixel(self):
        img = np.array([[100]], dtype=np.uint16)
        result = to_8bit(img)
        self.assertEqual(result.dtype, np.uint8)
        self.assertEqual(result[0, 0], 0)

    def test_preserves_shape(self):
        img = np.zeros((10, 20, 3), dtype=np.uint16)
        result = to_8bit(img)
        self.assertEqual(result.shape, (10, 20, 3))


if __name__ == '__main__':
    unittest.main()
