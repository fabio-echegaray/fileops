import numpy as np
import pytest
import skimage.util
from fileops.image.ops import rescale


class TestRescale:
    def test_no_rescale_no_gamma_returns_float(self):
        img = np.array([[0, 128], [255, 64]], dtype=np.uint16)
        settings = {"name": "ch1", "color": "red"}
        result = rescale(img, settings)
        # rescale always converts to float via img_as_float
        assert np.issubdtype(result.dtype, np.floating)
        np.testing.assert_array_equal(result, skimage.util.img_as_float(img))

    def test_rescale_bool_enables_percentile_rescale(self):
        img = np.array([[0, 50], [100, 200]], dtype=np.uint16)
        settings = {"rescale": True}
        result = rescale(img, settings)
        assert np.issubdtype(result.dtype, np.floating)
        assert result.max() == pytest.approx(1.0)

    def test_rescale_with_min_max(self):
        img = np.array([[0, 100], [200, 300]], dtype=np.uint16)
        settings = {"rescale": True, "rescale_min": 0, "rescale_max": 300}
        result = rescale(img, settings)
        assert np.issubdtype(result.dtype, np.floating)
        assert result.max() == pytest.approx(1.0)

    def test_rescale_dict_range(self):
        img = np.array([[0, 50], [100, 150]], dtype=np.float32)
        settings = {"rescale": {"range": (0, 150)}}
        result = rescale(img, settings)
        assert result.dtype == np.float32

    def test_gamma_adjustment(self):
        img = np.array([[0.0, 0.5], [1.0, 0.25]], dtype=np.float32)
        settings = {"gamma_value": 2.0, "gamma_gain": 1.0}
        result = rescale(img, settings)
        assert result.dtype == img.dtype
        # Gamma > 1 darkens midtones
        assert result[0, 1] < img[0, 1]

    def test_rescale_and_gamma_raises(self):
        img = np.array([[0, 1]], dtype=np.uint16)
        settings = {"rescale": True, "gamma_value": 1.0, "gamma_gain": 1.0}
        with pytest.raises(ValueError, match="Gamma values and rescale cannot be used at the same time"):
            rescale(img, settings)

    def test_as_original_dtype_uint8(self):
        img = np.array([[0, 128], [255, 64]], dtype=np.uint8)
        settings = {"rescale": True}
        result = rescale(img, settings, as_original_dtype=True)
        assert result.dtype == np.uint8
        assert result.max() == 255

    def test_as_original_dtype_uint16(self):
        img = np.array([[0, 128], [255, 64]], dtype=np.uint16)
        settings = {"rescale": True}
        result = rescale(img, settings, as_original_dtype=True)
        assert result.dtype == np.uint16
        assert result.max() == np.iinfo(np.uint16).max

    def test_as_original_dtype_float32(self):
        img = np.array([[0.0, 0.5], [1.0, 0.25]], dtype=np.float32)
        settings = {"rescale": True}
        result = rescale(img, settings, as_original_dtype=True)
        assert result.dtype == np.float32

    def test_does_not_modify_original(self):
        img = np.array([[0, 128], [255, 64]], dtype=np.uint16)
        original = img.copy()
        settings = {"rescale": True}
        rescale(img, settings)
        np.testing.assert_array_equal(img, original)

    def test_rescale_min_max_with_none_values(self):
        img = np.array([[0, 100], [200, 300]], dtype=np.uint16)
        settings = {"rescale": True, "rescale_min": None, "rescale_max": None}
        # None values for rescale_min/max cause int(None) to raise TypeError
        with pytest.raises(TypeError):
            rescale(img, settings)

    def test_input_not_modified_by_settings_mutation(self):
        img = np.array([[0, 128], [255, 64]], dtype=np.uint16)
        settings = {"rescale_min": 10, "rescale_max": 200}
        rescale(img, settings)
        assert "rescale" not in settings
