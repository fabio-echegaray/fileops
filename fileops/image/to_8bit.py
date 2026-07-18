import numpy as np


def to_8bit(img: np.ndarray) -> np.ndarray:
    img_min = img.min()
    img_max = img.max()
    if img_max == img_min:
        return np.zeros_like(img, dtype=np.uint8)
    img = (img - img_min) / (img_max - img_min) * 255
    img = img.astype(np.uint8)
    return img
