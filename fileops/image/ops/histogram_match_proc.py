from __future__ import annotations

from typing import TYPE_CHECKING

from fileops.image.imagemeta import metadataimage_like
from fileops.image.ops import image_match_histograms, rescale
from fileops.image.ops.image_processor import ImageProcessor

if TYPE_CHECKING:
    from fileops.image import MetadataImage, ImageFile


class HistogramMatchProcessor(ImageProcessor):
    """ performs histogram matching correction of z-projected frames """

    def __init__(self, reference_frame: int, *args, **kwargs):
        # super().__init__(*args, **kwargs)
        if type(reference_frame) is not int:
            raise ValueError

        self.reference_frame = reference_frame
        self.reference_img = {}

    def on_added(self, imf: ImageFile):
        self.imf = imf
        self.log.info(f"Adding histogram matching correction to {self.imf.image_path}.")

        # set reference image to perform histogram matching
        channels = self.imf.channel_subset if self.imf.channel_subset is not None else self.imf.channels
        for ch in channels:
            mdi = self.imf.z_projection(self.reference_frame, ch, projection='max', skip_proc=False)
            resc_img = rescale(mdi.image, {"rescale": True}, as_original_dtype=True)
            mdi_corrected = metadataimage_like(mdi, resc_img)
            self.reference_img[ch] = mdi_corrected

    def process(self, mdi: MetadataImage, *args, **kwargs) -> 'MetadataImage':
        if mdi.channel in self.reference_img:
            matched_img = image_match_histograms(mdi.image, self.reference_img[mdi.channel].image,
                                                 as_original_dtype=True)
            mdi_corrected = metadataimage_like(mdi, matched_img)
            return mdi_corrected
        else:
            return mdi
