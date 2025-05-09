import numpy as np
import os
import pandas as pd
import re
import tifffile as tf
from datetime import datetime, time
from pathlib import Path

from fileops.logger import get_logger
from ._mmanager_metadata import MetadataVersion10Mixin, mm_metadata_files
from .exceptions import FrameNotFoundError
from .image_file import ImageFile
from .imagemeta import MetadataImage


class MicroManagerSingleImageStack(ImageFile, MetadataVersion10Mixin):
    log = get_logger(name='MicroManagerSingleImageStack')

    def __init__(self, image_path: Path, **kwargs):
        # check whether this is the format that we recognise
        self._info = None
        if not self.has_valid_format(image_path):
            raise FileNotFoundError("Format is not correct.")

        super(MicroManagerSingleImageStack, self).__init__(image_path, **kwargs)

    @staticmethod
    def has_valid_format(path: Path):
        """check whether this is an image stack with the naming format from micromanager"""

        # image folder has to have only one metadata file at maximum
        m_names_match = mm_metadata_files(path.parent, path)
        if len(m_names_match) > 1:
            return False

        # check for data structures in tiff file
        with tf.TiffFile(path) as tif:
            if not hasattr(tif, "ome_metadata") or not tif.ome_metadata:
                return False
            if not hasattr(tif, "micromanager_metadata") or not tif.micromanager_metadata:
                return False
            if not tif.is_micromanager:
                return False
        return True

    @property
    def info(self) -> pd.DataFrame:
        if self._info is not None:
            return self._info

        path = self.image_path
        fname_stat = path.stat()
        fcreated = datetime.fromtimestamp(fname_stat.st_atime).strftime('%a %b/%d/%Y, %H:%M:%S')
        fmodified = datetime.fromtimestamp(fname_stat.st_mtime).strftime('%a %b/%d/%Y, %H:%M:%S')

        total_sec = int(self.time_interval * self.n_frames)
        total_min = int(total_sec / 60)
        dur_sec = total_sec % 60
        dur_min = total_min % 60
        total_hr = int(total_min / 60)
        dur_hr = total_hr % 24
        dur_day = int(total_hr / 24)

        self._info = {
            'folder':                            self.image_path.parent,
            'filename':                          self.image_path.name,
            'image_id':                          '',
            'image_name':                        path.parent.name,
            'instrument_id':                     '',
            'pixels_id':                         '',
            'channels':                          self.n_channels,
            'z-stacks':                          self.n_zstacks,
            'frames':                            self.n_frames,
            'delta_t':                           self.time_interval,
            'duration':                          time(hour=dur_hr, minute=dur_min, second=dur_sec),
            'width':                             self.width,
            'height':                            self.height,
            'data_type':                         None,
            # 'objective_id':                      "TINosePiece-Label",
            # 'magnification':                     int(
            #     re.search(r' ([0-9]*)x', meta["TINosePiece-Label"]).group(1)),
            'pixel_size':                        self.um_per_pix,
            'pixel_size_unit':                   'um',
            'pix_per_um':                        self.pix_per_um,
            'change (Unix), creation (Windows)': fcreated,
            'most recent modification':          fmodified,
        }

        self._info = pd.DataFrame(self._info, index=[0])
        return self._info

    def _image(self, plane, row=0, col=0, fid=0) -> MetadataImage:
        rgx = re.search(r'^c([0-9]*)z([0-9]*)t([0-9]*)$', plane)
        if rgx is None:
            raise FrameNotFoundError

        c, z, t = rgx.groups()
        t, c, z = int(t), int(c), int(z)

        key = f"c{c:0{len(str(self.n_channels))}d}z{z:0{len(str(self.n_zstacks))}d}t{t:0{len(str(self.n_frames))}d}"
        ix = self.all_planes_md_dict[key]

        filename = self.files[ix] if not self.error_loading_metadata else self.files[0]
        im_path = self.image_path.parent / filename

        # find all files previous to this frame to calculate number of indexes already visited
        fprev_set = set(np.unique(self.files[:ix + 1])) - set([filename])
        idx_prev = np.sum(self.frames_per_file[f] for f in fprev_set)
        ix -= idx_prev

        if not os.path.exists(im_path):
            self.log.error(f'Frame, channel, z ({t},{c},{z}) not found in file.')
            raise FrameNotFoundError(f'Frame, channel, z ({t},{c},{z}) not found in file.')

        with tf.TiffFile(im_path) as tif:
            if ix >= len(tif.pages):
                self.log.error(f'Frame, channel, z ({t},{c},{z}) not found in file.')
                raise FrameNotFoundError(f'Frame, channel, z ({t},{c},{z}) not found in file.')

        image = tif.pages[ix].asarray()
        t_int = self.timestamps[t] - self.timestamps[t - 1] if t > 0 else self.timestamps[t]
        return MetadataImage(reader='MicroManagerStack',
                             image=image,
                             pix_per_um=self.pix_per_um, um_per_pix=self.um_per_pix,
                             time_interval=t_int,
                             timestamp=self.timestamps[t],
                             frame=t, channel=c, z=z, width=self.width, height=self.height,
                             intensity_range=[np.min(image), np.max(image)])
