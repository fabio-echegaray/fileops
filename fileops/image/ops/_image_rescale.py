import copy

import numpy as np
import skimage
from skimage import exposure


def normalize_to_dtype(img: np.ndarray, dtype: np.dtype) -> np.ndarray:
    if img.dtype == dtype:
        return img
    if np.issubdtype(img.dtype, np.floating):
        if np.issubdtype(dtype, np.integer):
            return (img * np.iinfo(dtype).max).astype(dtype)
    elif np.issubdtype(dtype, np.integer):
        return (img.astype(np.float64) * np.iinfo(dtype).max / np.iinfo(img.dtype).max).astype(dtype)
    return img.astype(dtype)


def rescale(img: np.array, settings, as_original_dtype=False) -> np.array:
    dtype = img.dtype
    img = skimage.util.img_as_float(img)
    _stn = copy.copy(settings)
    if 'rescale_min' in _stn and 'rescale_max' in _stn:
        _stn['rescale'] = True
        _stn['rescale_min'] = int(_stn['rescale_min'])
        _stn['rescale_max'] = int(_stn['rescale_max'])
    if 'rescale' in _stn and ('gamma_value' in _stn or 'gamma_gain' in _stn):
        raise ValueError("Gamma values and rescale cannot be used at the same time")
    if 'rescale' in _stn and _stn['rescale']:
        if type(_stn['rescale']) is dict:
            mini, maxi = _stn['rescale']['range']
            img = exposure.rescale_intensity(img, in_range=(mini, maxi))
        elif type(_stn['rescale']) is bool and _stn['rescale']:
            p_min, p_max = np.percentile(img, (1, 99))
            i_min = _stn['rescale_min'] / np.iinfo(dtype).max \
                if 'rescale_min' in _stn and _stn['rescale_min'] is not None else p_min
            i_max = _stn['rescale_max'] / np.iinfo(dtype).max \
                if 'rescale_max' in _stn and _stn['rescale_max'] is not None else p_max
            img = exposure.rescale_intensity(img, in_range=(i_min, i_max))
    if 'gamma_value' in _stn and 'gamma_gain' in _stn:
        img = exposure.adjust_gamma(img, gamma=_stn['gamma_value'], gain=_stn['gamma_gain'])

    if as_original_dtype:
        img = normalize_to_dtype(img, dtype)

    return img
