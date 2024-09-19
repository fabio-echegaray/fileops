from pathlib import Path

import numpy as np
import tifffile as tf
from bs4 import BeautifulSoup as bs

from fileops.image._image_file_ome import OMEImageFile
from fileops.image._tifffile_imagej_metadata import MetadataImageJTifffileMixin
from fileops.image.imagemeta import MetadataImage
from fileops.logger import get_logger

import bioio_base as biob

class TifffileOMEImageFile(OMEImageFile, MetadataImageJTifffileMixin):
    log = get_logger(name='TifffileOMEImageFile')

    def __init__(self, image_path: Path, **kwargs):
        super(TifffileOMEImageFile, self).__init__(image_path, **kwargs)

        self._rdr: biob.reader.Reader = None

        self.md_xml = self._tif.ome_metadata
        if self.md_xml:
            self.md = bs(self.md_xml, "lxml-xml")

        self._fix_defaults(failover_dt=self._failover_dt, failover_mag=self._failover_mag)

    @staticmethod
    def has_valid_format(path: Path):
        if path.exists():
            with tf.TiffFile(path) as _tif:
                has_ome_meta = hasattr(_tif, "ome_metadata") and _tif.ome_metadata is not None
                return has_ome_meta

    def ix_at(self, c, z, t):
        czt_str = self.plane_at(c, z, t)
        if czt_str in self.all_planes_md_dict:
            return self.all_planes_md_dict[czt_str][0]
        self.log.warning(f"No index found for c={c}, z={z}, and t={t}.")

    def _image(self, plane_ix, row=0, col=0, fid=0) -> MetadataImage:  # PLANE HAS METADATA INFO OF THE IMAGE PLANE
        page, c, z, t = self.all_planes_md_dict[plane_ix]
        # logger.debug('retrieving image id=%d row=%d col=%d fid=%d' % (_id, row, col, fid))
        image = self._tif.pages[page].asarray()

        return MetadataImage(reader='OME',
                             image=image,
                             pix_per_um=1. / self.um_per_pix, um_per_pix=self.um_per_pix,
                             time_interval=self._md_deltaT_ms,
                             timestamp=self._md_deltaT_ms * t,
                             frame=int(t), channel=int(c), z=int(z), width=self.width, height=self.height,
                             intensity_range=[np.min(image), np.max(image)])
