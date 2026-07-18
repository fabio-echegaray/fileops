from __future__ import annotations

from typing import TYPE_CHECKING

from fileops.export.config_channel_section import channel_configuration
from fileops.image.imagemeta import metadataimage_like
from fileops.image.ops import ImageProcessor, rescale

if TYPE_CHECKING:
    from fileops.image import ImageFile, MetadataImage


class RescaleProcessor(ImageProcessor):
    """ performs intensity rescaling of z-projected frames """

    def __init__(self, settings, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._ch_par = settings
        self._ch_cfg = channel_configuration(settings)

    def on_added(self, imf: ImageFile):
        self.imf = imf
        self.log.info(f"Adding intensity rescaling to {self.imf.image_path}.")

    def process(self, mdi: MetadataImage, *args, **kwargs) -> 'MetadataImage':
        settings = self._ch_cfg[self._ch_par[mdi.channel]["name"]]
        resc_img = rescale(mdi.image, settings, as_original_dtype=True)
        mdi_corrected = metadataimage_like(mdi, resc_img)
        return mdi_corrected
