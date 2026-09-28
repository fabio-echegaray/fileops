import unittest

import tifffile as tf

from fileops.image._utils import resolve_pix_per_um_from_tiff_tags


class _Tag:
    def __init__(self, value):
        self.value = value


class _FakePage:
    """Minimal stand-in for a `tifffile` page exposing only the resolution tags."""

    def __init__(self, xresolution, resunit):
        self.tags = {'XResolution': _Tag(xresolution), 'ResolutionUnit': _Tag(resunit)}


class TestResolvePixPerUmFromTiffTags(unittest.TestCase):

    def test_missing_xresolution_returns_1(self):
        page = _FakePage(None, tf.RESUNIT.CENTIMETER)
        del page.tags['XResolution']
        self.assertEqual(resolve_pix_per_um_from_tiff_tags(page), 1.0)

    def test_micromanager_sentinel_returns_1(self):
        # MicroManager marks "no pixel-size calibration" with XResolution = 2**32 - 1.
        page = _FakePage((4294967295, 1), tf.RESUNIT.CENTIMETER)
        self.assertEqual(resolve_pix_per_um_from_tiff_tags(page), 1.0)

    def test_cm_resolution_is_converted_to_pixels_per_um(self):
        # 10000 px/cm == 1 px/um.
        page = _FakePage((10000, 1), tf.RESUNIT.CENTIMETER)
        self.assertAlmostEqual(resolve_pix_per_um_from_tiff_tags(page), 1.0)

    def test_non_cm_resolution_is_not_divided(self):
        page = _FakePage((5, 1), tf.RESUNIT.INCH)
        self.assertAlmostEqual(resolve_pix_per_um_from_tiff_tags(page), 5.0)

    def test_zero_denominator_returns_1(self):
        page = _FakePage((10, 0), tf.RESUNIT.CENTIMETER)
        self.assertEqual(resolve_pix_per_um_from_tiff_tags(page), 1.0)

    def test_absurd_calibration_returns_1(self):
        page = _FakePage((10000000000, 1), tf.RESUNIT.CENTIMETER)
        self.assertEqual(resolve_pix_per_um_from_tiff_tags(page), 1.0)


if __name__ == '__main__':
    unittest.main()