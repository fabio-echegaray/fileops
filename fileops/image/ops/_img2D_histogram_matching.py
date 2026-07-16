import numpy as np
from skimage.exposure import match_histograms


def image_match_histograms(image: np.array, reference_image: np.array, as_original_dtype=False) -> np.array:
    """
    Matches the intensity distribution of image to the distribution of reference_image.
    :param image: numpy array of image to be modified
    :param reference_image: numpy array of the reference image
    :param as_original_dtype: True if the output data type has to match source image
    :return: numpy array of same dimensions than image and with matched histogram of reference_image
    """

    dtype = image.dtype

    matched = match_histograms(image, reference_image)

    if as_original_dtype:
        matched = matched.astype(dtype)

    return matched
