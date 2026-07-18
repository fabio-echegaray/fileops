import numpy as np
import pytest


@pytest.fixture
def img_uint8():
    return np.array([[0, 128], [255, 64]], dtype=np.uint8)


@pytest.fixture
def img_uint16():
    return np.array([[0, 32768], [65535, 16384]], dtype=np.uint16)


@pytest.fixture
def img_float32():
    return np.array([[0.0, 0.5], [1.0, 0.25]], dtype=np.float32)


@pytest.fixture
def img_zeros():
    return np.zeros((4, 4), dtype=np.uint16)
