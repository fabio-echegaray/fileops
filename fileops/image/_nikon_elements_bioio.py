import json
import logging
import re
from pathlib import Path
from typing import Tuple

import bioio_base
import bioio_base.exceptions
import bioio_nd2
import numpy as np
import pandas as pd
from bioio import BioImage
from bioio_base.standard_metadata import StandardMetadata
from ome_types import OME

from fileops.image import OMEImageFile
from fileops.image._ome_channel_json_encoder import JSONChannelEncoder
from fileops.image.exceptions import FrameNotFoundError
from fileops.image.imagemeta import MetadataImage
from fileops.logger import get_logger

logging.getLogger("fsspec.local").setLevel(logging.INFO)


class BioioNikonImageFile(OMEImageFile):
    log = get_logger(name='BioioNikonImageFile')

    def __init__(self, image_path: Path, image_series: int = 0, **kwargs):
        self.image_path = image_path
        md, md_ome = self._get_metadata()

        self.md, self.md_ome = md, md_ome

        self.all_series = self._rdr.scenes
        self.instrument_md = md_ome.instruments
        self.objectives_md = self.instrument_md[0].objectives
        self.log.info(f"All series: {self._rdr.scenes}.")

        super(BioioNikonImageFile, self).__init__(image_path, image_series=image_series, **kwargs)

    @staticmethod
    def has_valid_format(path: Path):
        try:
            nd2_img = BioImage(path, reader=bioio_nd2.Reader)
            assert len(nd2_img.scenes) > 0 or len(nd2_img.channel_names) > 0
            del nd2_img
        except bioio_base.exceptions.UnsupportedFileFormatError:
            return False

        return True

    def _load_imageseries(self, series: int):
        if self.md_ome is None:
            return
        self._rdr.set_scene(self._series)
        super()._load_imageseries(series)

    @property
    def info_channels(self) -> pd.DataFrame:
        channels_info = list()
        for k, _series in enumerate(self.all_series):  # iterate through all series
            self._rdr.set_scene(_series)
            md_ome = self._rdr.ome_metadata

            channels_info.extend([json.dumps(ch, cls=JSONChannelEncoder)
                                  for im in md_ome.images for ch in im.pixels.channels])

        self._rdr.set_scene(self._series)  # set series back to what it was before querying other series

        out = pd.DataFrame(json.loads(chi) for chi in channels_info)
        out.drop(columns=['pockel_cell_setting', 'annotation_refs', 'detector_settings', 'filter_set_ref',
                          'light_path', 'light_source_settings'], inplace=True)
        out.drop_duplicates(inplace=True, ignore_index=True)
        return out

    def ix_at(self, c, z, t):
        czt_str = self.plane_at(c, z, t)
        if czt_str in self.all_planes_md_dict:
            return self.all_planes_md_dict[czt_str]
        self.log.warning(f"No index found for c={c}, z={z}, and t={t}.")
        return None

    def _zcube(self, plane, zsubset=None) -> MetadataImage:
        rgx = re.search(r'^c([0-9]*)z([0-9]*)t([0-9]*)$', plane)
        if rgx is None:
            raise FrameNotFoundError

        c, z, t = rgx.groups()
        c, z, t = int(c), int(z), int(t)
        self._rdr.set_scene(self._series)  # for some reason the reader changes the scene...
        self.log.debug(f'retrieving volume c={c:d} t={t:d} series={self._series:d}')
        self.log.debug(f"img scene {self._rdr.current_scene} ImageFile series {self._series}")

        # obtain 5D TCZYX xarray data array backed by dask array to then fetch the required slice
        dask_array = self._rdr.get_image_dask_data("ZYX", C=c, T=t)
        zss = sorted(zsubset) if zsubset is not None else self.zstacks
        image = dask_array[zss, :, :].compute()

        return MetadataImage(reader='BioIO',
                             image=image,
                             pix_per_um=1. / self.um_per_pix, um_per_pix=self.um_per_pix,
                             time_interval=None,
                             timestamp=self.time_interval,
                             frame=int(t), channel=int(c), z=int(z), width=self.width, height=self.height,
                             intensity_range=[np.min(image), np.max(image)])

    def _image(self, plane, row=0, col=0, fid=0) -> MetadataImage:
        rgx = re.search(r'^c([0-9]*)z([0-9]*)t([0-9]*)$', plane)
        if rgx is None:
            raise FrameNotFoundError

        c, z, t = rgx.groups()
        c, z, t = int(c), int(z), int(t)
        self._rdr.set_scene(self._series)  # for some reason the reader changes the scene...
        self.log.spam(f'retrieving image c={c:d} z={z:d} t={t:d} series={self._series:d}')
        self.log.spam(f"img scene {self._rdr.current_scene} ImageFile series {self._series}")

        # obtain 5D TCZYX xarray data array backed by dask array to then fetch the required slice
        dask_array = self._rdr.get_image_dask_data("ZYX", C=c, T=t)
        image = dask_array[z, :, :].compute()

        return MetadataImage(reader='BioIO',
                             image=image,
                             pix_per_um=1. / self.um_per_pix, um_per_pix=self.um_per_pix,
                             time_interval=None,
                             timestamp=self.time_interval,
                             frame=int(t), channel=int(c), z=int(z), width=self.width, height=self.height,
                             intensity_range=[np.min(image), np.max(image)])

    def _get_metadata(self) -> Tuple[StandardMetadata, OME]:
        nd2_img = BioImage(self.image_path.as_posix(), reader=bioio_nd2.Reader)
        md = nd2_img.standard_metadata
        md_ome = nd2_img.ome_metadata
        self._rdr = nd2_img
        self._rdr.set_scene(self._series)

        return md, md_ome
