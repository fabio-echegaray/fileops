import numpy as np

from fileops.image.to_8bit import to_8bit


class TestTo8Bit:
    def test_uint8_passthrough(self, img_uint8):
        result = to_8bit(img_uint8)
        assert result.dtype == np.uint8
        assert result.shape == img_uint8.shape

    def test_uint16_scaled(self, img_uint16):
        result = to_8bit(img_uint16)
        assert result.dtype == np.uint8
        assert result.max() == 255

    def test_float32_scaled(self, img_float32):
        result = to_8bit(img_float32)
        assert result.dtype == np.uint8
        assert result.max() == 255

    def test_zeros_returns_zeros(self, img_zeros):
        result = to_8bit(img_zeros)
        assert result.dtype == np.uint8
        assert result.sum() == 0

    def test_all_same_value(self):
        img = np.full((3, 3), 42, dtype=np.uint16)
        result = to_8bit(img)
        assert result.dtype == np.uint8
        # When all values equal, max is nonzero so division works
        assert np.all(result == 255)

    def test_single_pixel(self):
        img = np.array([[100]], dtype=np.uint16)
        result = to_8bit(img)
        assert result.dtype == np.uint8
        assert result[0, 0] == 255

    def test_preserves_shape(self):
        img = np.zeros((10, 20, 3), dtype=np.uint16)
        result = to_8bit(img)
        assert result.shape == (10, 20, 3)
