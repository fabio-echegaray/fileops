import tifffile as tf

from fileops.image._cache_metadata import load_metadata_from_disk, save_metadata_to_disk, normalize_plane_keys


class TiffMetadataMixinBase:
    """Base mixin providing shared metadata-load and pickle boilerplate.

    Subclasses must implement ``_load_metadata()`` which populates instance
    attributes from the TIFF file stored in ``self.image_path``.
    """

    def _init_metadata(self):
        """Load cached metadata or run ``_load_metadata()`` and cache the result."""
        self.error_loading_metadata = False
        self._tif = None
        if load_metadata_from_disk(self):
            self._tif = tf.TiffFile(self.image_path)
            # Normalize zero-padding of the cached plane keys
            normalize_plane_keys(self)
        else:
            self._load_metadata()
            save_metadata_to_disk(self)
            self.log.info(f"Compiled metadata of file {self.image_path.name} saved to disk.")

    def __getstate__(self):
        state = self.__dict__.copy()
        state.pop('_tif', None)
        return state

    def __setstate__(self, state):
        self.__dict__.update(state)
        self._tif = tf.TiffFile(self.image_path)
