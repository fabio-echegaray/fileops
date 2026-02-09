import numpy as np

from scipy.optimize import curve_fit


def bleach_func(x, a, b, c):
    return a * np.exp(-b * x) + c


def photobleach_correct(mean_intensities: np.array) -> np.array:
    xdata = np.array(range(len(mean_intensities)))

    ui16_max = np.iinfo(np.uint16).max
    popt, pcov = curve_fit(bleach_func, xdata, mean_intensities, bounds=(0, [ui16_max, 1., ui16_max]))

    return popt
