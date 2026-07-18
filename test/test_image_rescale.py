import numpy as np
import pytest

from fileops.image.ops._image_rescale import rescale


class TestRescale:
    def test_no_rescale_no_gamma_returns_float(self, img_uint16):
        result = rescale(img_uint16, {})
        assert result.dtype == np.float64

    def test_rescale_bool_enables_percentile_rescale(self, img_uint16):
        result = rescale(img_uint16, {'rescale': True})
        assert result.max() <= 1.0
        assert result.min() >= 0.0

    def test_rescale_with_min_max(self, img_uint16):
        result = rescale(img_uint16, {'rescale': True, 'rescale_min': 0, 'rescale_max': 65535})
        assert result.max() <= 1.0

    def test_rescale_dict_range(self, img_uint16):
        result = rescale(img_uint16, {'rescale': {'range': (0, 65535)}})
        assert result.max() <= 1.0

    def test_gamma_adjustment(self, img_float32):
        result = rescale(img_float32, {'gamma_value': 0.5, 'gamma_gain': 1.0})
        assert np.issubdtype(result.dtype, np.floating)
        assert result.max() <= 1.0

    def test_rescale_and_gamma_raises(self, img_uint16):
        with pytest.raises(ValueError, match="Gamma values and rescale cannot be used"):
            rescale(img_uint16, {'rescale': True, 'gamma_value': 0.5, 'gamma_gain': 1.0})

    def test_as_original_dtype_uint16(self, img_uint16):
        result = rescale(img_uint16, {'rescale': True}, as_original_dtype=True)
        assert result.dtype == np.uint16

    def test_as_original_dtype_float32(self, img_float32):
        result = rescale(img_float32, {}, as_original_dtype=True)
        assert result.dtype == np.float32

    def test_does_not_modify_original(self, img_uint16):
        original = img_uint16.copy()
        rescale(img_uint16, {'rescale': True})
        np.testing.assert_array_equal(img_uint16, original)

    def test_rescale_min_max_with_none_values_raises(self, img_uint16):
        with pytest.raises(TypeError):
            rescale(img_uint16, {'rescale': True, 'rescale_min': None, 'rescale_max': None})
