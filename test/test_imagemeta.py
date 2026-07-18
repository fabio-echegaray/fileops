import numpy as np

from fileops.image.imagemeta import MetadataImage, MetadataImageSeries, metadataimage_like


class TestMetadataImage:
    def test_creation(self):
        mdi = MetadataImage(
            reader="test", image=None, pix_per_um=1.0, um_per_pix=1.0,
            time_interval=1.0, frame=0, channel=0, z=0,
            width=100, height=100, timestamp=None, intensity_range=(0, 65535)
        )
        assert mdi.reader == "test"
        assert mdi.width == 100
        assert mdi.intensity_range == (0, 65535)

    def test_is_namedtuple(self):
        mdi = MetadataImage(
            reader=None, image=None, pix_per_um=None, um_per_pix=None,
            time_interval=None, frame=None, channel=None, z=None,
            width=None, height=None, timestamp=None, intensity_range=None
        )
        assert hasattr(mdi, '_fields')
        assert 'reader' in mdi._fields
        assert 'image' in mdi._fields


class TestMetadataImageSeries:
    def test_creation(self):
        series = MetadataImageSeries(
            reader="test", images=[], pix_per_um=1.0, um_per_pix=1.0,
            um_per_z=0.5, time_interval=1.0, frames=[0, 1],
            channels=[0], zstacks=[0], width=100, height=100,
            series=0, timestamps=[], intensity_ranges=[], axes="CYX"
        )
        assert series.frames == [0, 1]
        assert series.axes == "CYX"


class TestMetadataimageLike:
    def test_creates_copy_with_new_image(self):
        img = np.zeros((10, 10))
        mdi = MetadataImage(
            reader="test", image=img, pix_per_um=2.0, um_per_pix=0.5,
            time_interval=0.1, frame=5, channel=1, z=3,
            width=10, height=10, timestamp="now", intensity_range=(0, 100)
        )
        new_img = np.ones((20, 20))
        new_mdi = metadataimage_like(mdi, new_img)

        assert new_mdi.image is new_img
        assert new_mdi.reader == "test"
        assert new_mdi.pix_per_um == 2.0
        assert new_mdi.frame == 5
        assert new_mdi.width == 10

    def test_does_not_mutate_original(self):
        mdi = MetadataImage(
            reader="r", image="old", pix_per_um=1.0, um_per_pix=1.0,
            time_interval=1.0, frame=0, channel=0, z=0,
            width=10, height=10, timestamp=None, intensity_range=None
        )
        new_mdi = metadataimage_like(mdi, "new")
        assert mdi.image == "old"
        assert new_mdi.image == "new"
