import numpy as np
import pytest

from fileops.image.ops._bleach_correction import bleach_func, photobleach_fit


class TestBleachFunc:
    def test_exponential_decay(self):
        result = bleach_func(0, a=100, b=0.1, c=10)
        assert result == pytest.approx(110.0)

    def test_large_x_approaches_c(self):
        result = bleach_func(1000, a=100, b=0.1, c=10)
        assert result == pytest.approx(10.0, abs=1e-10)

    def test_array_input(self):
        x = np.array([0, 1, 2])
        result = bleach_func(x, a=100, b=0.1, c=10)
        assert result.shape == (3,)
        assert result[0] > result[1] > result[2]


class TestPhotobleachFit:
    def test_fit_returns_three_params(self):
        x = np.arange(20, dtype=float)
        data = 1000 * np.exp(-0.1 * x) + 100
        popt = photobleach_fit(data)
        assert len(popt) == 3

    def test_fit_a_is_positive(self):
        x = np.arange(20, dtype=float)
        data = 1000 * np.exp(-0.1 * x) + 100
        popt = photobleach_fit(data)
        assert popt[0] > 0  # amplitude

    def test_fit_b_is_positive(self):
        x = np.arange(20, dtype=float)
        data = 1000 * np.exp(-0.1 * x) + 100
        popt = photobleach_fit(data)
        assert popt[1] > 0  # decay rate
