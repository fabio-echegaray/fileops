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
import nd2
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
        self._nd2_file = None
        self._nd2_frame_index = None
        self._nd2_position_index = None
        self._nd2_has_channel_loop = False
        self._use_bioio_planes = False
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
        except (bioio_base.exceptions.UnsupportedFileFormatError, OSError, IOError):
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

    def _image(self, plane, row=0, col=0, fid=0) -> MetadataImage:
        rgx = re.search(r'^c([0-9]*)z([0-9]*)t([0-9]*)$', plane)
        if rgx is None:
            raise FrameNotFoundError

        c, z, t = rgx.groups()
        c, z, t = int(c), int(z), int(t)

        image = self._read_plane(c, z, t)

        return MetadataImage(reader='BioIO',
                             image=image,
                             pix_per_um=1. / self.um_per_pix, um_per_pix=self.um_per_pix,
                             time_interval=None,
                             timestamp=self.time_interval,
                             frame=int(t), channel=int(c), z=int(z), width=self.width, height=self.height,
                             intensity_range=[int(image.min()), int(image.max())])

    def _read_plane(self, c: int, z: int, t: int) -> np.ndarray:
        if self._nd2_file is None:
            self._nd2_file = nd2.ND2File(self.image_path)
            self._nd2_has_channel_loop = any('C' in li for li in self._nd2_file.loop_indices)
            if self._nd2_file.is_rgb:
                self._use_bioio_planes = True
                self.log.warning("nd2 direct plane reading unavailable for rgb files; "
                                 "falling back to the bioio engine.")
            else:
                def _nd2_key(li):
                    t_, z_, c_ = li.get('T', 0), li.get('Z', 0), li.get('C', 0)
                    p = li.get('P', 0)
                    return (p, t_, z_, c_) if self._nd2_has_channel_loop else (p, t_, z_)

                self._nd2_frame_index = {_nd2_key(li): i for i, li in enumerate(self._nd2_file.loop_indices)}
                if self._nd2_position_index is None:
                    series = getattr(self, '_series', None)
                    name = self.all_series[series] if self.all_series and isinstance(series, int) \
                        and series < len(self.all_series) else None
                    m = re.match(r'XYPos:(\d+)', str(name)) if name is not None else None
                    self._nd2_position_index = int(m.group(1)) if m else (series or 0)

        if self._use_bioio_planes:
            self._rdr.set_scene(self._series)
            return self._rdr.get_image_data("ZYX", Z=z, C=c, T=t).reshape(1, self.width, self.height)[0]

        p = self._nd2_position_index or 0
        key = (p, t, z, c) if self._nd2_has_channel_loop else (p, t, z)
        try:
            frame = self._nd2_file.read_frame(self._nd2_frame_index[key])
        except (KeyError, TypeError, IndexError):
            self.log.warning("nd2 direct plane reading failed; falling back to the bioio engine.")
            self._use_bioio_planes = True
            self._rdr.set_scene(self._series)
            return self._rdr.get_image_data("ZYX", Z=z, C=c, T=t).reshape(1, self.width, self.height)[0]

        if self._nd2_has_channel_loop:
            img = frame.reshape(self.height, self.width)
        elif frame.ndim > 2:
            img = frame[c]
        else:
            img = frame
        return np.ascontiguousarray(img, dtype=frame.dtype)

    def close(self):
        try:
            if self._nd2_file is not None:
                self._nd2_file.close()
        except Exception:
            self.log.debug("error closing the nd2 handle", exc_info=True)
        finally:
            self._nd2_file = None
            self._nd2_frame_index = None
            self._nd2_position_index = None
        try:
            close = getattr(getattr(self, '_rdr', None), 'close', None)
            if callable(close):
                close()
        except Exception:
            self.log.debug("error closing the bioio handle", exc_info=True)

    def __del__(self):
        self.close()

    def _get_metadata(self) -> Tuple[StandardMetadata, OME]:
        nd2_img = BioImage(self.image_path.as_posix(), reader=bioio_nd2.Reader)
        md = nd2_img.standard_metadata
        md_ome = nd2_img.ome_metadata
        self._rdr = nd2_img
        self._rdr.set_scene(self._series)

        return md, md_ome
