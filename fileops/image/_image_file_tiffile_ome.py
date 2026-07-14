import re
from pathlib import Path

import bioio_base as biob
import numpy as np
import tifffile as tf
from ome_types import from_xml

from fileops.cached import cached_step
from fileops.image._image_file_ome import OMEImageFile
from fileops.image._tifffile_imagej_metadata import MetadataImageJTifffileMixin
from fileops.image.exceptions import FrameNotFoundError
from fileops.image.imagemeta import MetadataImage
from fileops.logger import get_logger


class TifffileOMEImageFile(OMEImageFile, MetadataImageJTifffileMixin):
    log = get_logger(name='TifffileOMEImageFile')

    def __init__(self, image_path: Path, **kwargs):
        # this calls all constructors up to OMEImageFile
        super(OMEImageFile, self).__init__(image_path, **kwargs)

        self._rdr: biob.reader.Reader = None

        self.md_xml = self._tif.ome_metadata
        if self.md_xml:
            ome_md_path = self.image_path.parent / f"{self.image_path.name}.fileops.ome_metadata.safe_to_delete.gz"
            self.md_ome = cached_step(ome_md_path, from_xml, self.md_xml)  # parsing XML takes quite a long time

        # this calls all constructors up to TifffileOMEImageFile
        super(TifffileOMEImageFile, self).__init__(image_path, **kwargs)

    @staticmethod
    def has_valid_format(path: Path):
        if path.exists():
            with tf.TiffFile(path) as _tif:
                has_ome_meta = hasattr(_tif, "ome_metadata") and _tif.ome_metadata is not None
                return has_ome_meta
        return False

    def ix_at(self, c, z, t):
        czt_str = self.plane_at(c, z, t)
        if czt_str in self.all_planes_md_dict:
            return self.all_planes_md_dict[czt_str]
        self.log.warning(f"No index found for c={c}, z={z}, and t={t}.")
        return None

    def _image(self, plane_ix, row=0, col=0, fid=0) -> MetadataImage:  # PLANE HAS METADATA INFO OF THE IMAGE PLANE
        page = self.all_planes_md_dict[plane_ix]
        rgx = re.search(r'^c([0-9]*)z([0-9]*)t([0-9]*)$', plane_ix)
        if rgx is None:
            raise FrameNotFoundError

        c, z, t = rgx.groups()
        t, c, z = int(t), int(c), int(z)

        # logger.debug('retrieving image id=%d row=%d col=%d fid=%d' % (_id, row, col, fid))
        try:
            image = self._tif.pages[page].asarray()
        except IndexError as e:
            raise FrameNotFoundError

        return MetadataImage(reader='OME',
                             image=image,
                             pix_per_um=1. / self.um_per_pix, um_per_pix=self.um_per_pix,
                             time_interval=self.time_interval,
                             timestamp=self.time_interval * t,
                             frame=int(t), channel=int(c), z=int(z), width=self.width, height=self.height,
                             intensity_range=[np.min(image), np.max(image)] if image.size > 0 else [np.nan, np.nan])
