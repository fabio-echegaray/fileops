import unittest
import numpy as np

from fileops.image.imagemeta import MetadataImage, MetadataImageSeries, metadataimage_like


class TestMetadataImage(unittest.TestCase):

    def test_creation(self):
        mdi = MetadataImage(
            reader="test", image=None, pix_per_um=1.0, um_per_pix=1.0,
            time_interval=1.0, frame=0, channel=0, z=0,
            width=100, height=100, timestamp=None, intensity_range=(0, 65535)
        )
        self.assertEqual(mdi.reader, "test")
        self.assertEqual(mdi.width, 100)
        self.assertEqual(mdi.intensity_range, (0, 65535))

    def test_is_namedtuple(self):
        mdi = MetadataImage(
            reader=None, image=None, pix_per_um=None, um_per_pix=None,
            time_interval=None, frame=None, channel=None, z=None,
            width=None, height=None, timestamp=None, intensity_range=None
        )
        self.assertTrue(hasattr(mdi, '_fields'))
        self.assertIn('reader', mdi._fields)
        self.assertIn('image', mdi._fields)


class TestMetadataImageSeries(unittest.TestCase):

    def test_creation(self):
        series = MetadataImageSeries(
            reader="test", images=[], pix_per_um=1.0, um_per_pix=1.0,
            um_per_z=0.5, time_interval=1.0, frames=[0, 1],
            channels=[0], zstacks=[0], width=100, height=100,
            series=0, timestamps=[], intensity_ranges=[], axes="CYX"
        )
        self.assertEqual(series.frames, [0, 1])
        self.assertEqual(series.axes, "CYX")


class TestMetadataimageLike(unittest.TestCase):

    def test_creates_copy_with_new_image(self):
        img = np.zeros((10, 10))
        mdi = MetadataImage(
            reader="test", image=img, pix_per_um=2.0, um_per_pix=0.5,
            time_interval=0.1, frame=5, channel=1, z=3,
            width=10, height=10, timestamp="now", intensity_range=(0, 100)
        )
        new_img = np.ones((20, 20))
        new_mdi = metadataimage_like(mdi, new_img)

        self.assertIs(new_mdi.image, new_img)
        self.assertEqual(new_mdi.reader, "test")
        self.assertEqual(new_mdi.pix_per_um, 2.0)
        self.assertEqual(new_mdi.frame, 5)
        self.assertEqual(new_mdi.width, 10)

    def test_does_not_mutate_original(self):
        mdi = MetadataImage(
            reader="r", image="old", pix_per_um=1.0, um_per_pix=1.0,
            time_interval=1.0, frame=0, channel=0, z=0,
            width=10, height=10, timestamp=None, intensity_range=None
        )
        new_mdi = metadataimage_like(mdi, "new")
        self.assertEqual(mdi.image, "old")
        self.assertEqual(new_mdi.image, "new")


if __name__ == '__main__':
    unittest.main()
