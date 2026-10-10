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

    def update_settings(self, settings) -> None:
        """Re-derive the per-channel configuration from *settings*.

        The processor is normally built once from the [DATA]-level channel
        parameters and shared across every section of a configuration file.
        Per-section ``gamma_*``/``rescale_*`` overrides only live in that
        section's merged ``channel_render_parameters``, so callers reconfigure
        this processor at render time with those settings before pulling frames.
        """
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


def configure_rescale_processor(imf: ImageFile, channel_render_parameters) -> None:
    """Point *imf*'s RescaleProcessor at *channel_render_parameters*.

    Section-level ``gamma_*``/``rescale_*`` overrides are merged into the
    section's channel parameters but never reach the [DATA]-level processor
    built in config_data_section.py. Rendering therefore ignored them. This
    helper reconfigures the (shared) processor at render time, creating it on
    demand when a section supplies gamma/rescale settings the [DATA] level did
    not enable. Call it once per section before that section pulls any frames.
    """
    has_settings = any(
        any('gamma' in k or 'rescale' in k for k in ch_cfg)
        for ch_cfg in channel_render_parameters.values()
    )
    for proc in imf.processing_deque:
        if isinstance(proc, RescaleProcessor):
            proc.update_settings(channel_render_parameters)
            return
    if has_settings:
        imf.add_processor(RescaleProcessor(channel_render_parameters))
