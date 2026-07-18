import numpy as np


def to_8bit(img: np.ndarray) -> np.ndarray:
    img_max = img.max()
    if img_max == 0:
        return img.astype(np.uint8)
    img = img / img_max * 255  # normalizes data in range 0 - 255
    img = img.astype(np.uint8)
    return img
