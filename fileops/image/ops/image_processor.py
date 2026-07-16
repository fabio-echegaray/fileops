from __future__ import annotations

from typing import TYPE_CHECKING

from fileops import get_logger

if TYPE_CHECKING:
    from fileops.image import MetadataImage, ImageFile


class ImageProcessor:
    """ base class for image processing operations on ImageFile """
    log = get_logger(name='ImageProcessor')
    imf: ImageFile

    def on_added(self, imf: ImageFile):
        raise NotImplementedError

    def process(self, mdi: MetadataImage, *args, **kwargs) -> 'MetadataImage':
        raise NotImplementedError
