import os
import pathlib
import re
from datetime import datetime

import numpy as np
import pandas as pd
import tifffile as tf

from fileops.image._mmanager_metadata import MetadataVersion10Mixin
from fileops.image.exceptions import FrameNotFoundError
from fileops.image.image_file import ImageFile
from fileops.image.imagemeta import MetadataImage
from fileops.logger import get_logger


class MicroManagerSingleImageStack(ImageFile, MetadataVersion10Mixin):
    log = get_logger(name='MicroManagerSingleImageStack')

    def __init__(self, image_path: str = None, **kwargs):
        # check whether this is a folder with images and take the folder they are in as position
        if not self.has_valid_format(image_path):
            raise FileNotFoundError("Format is not correct.")

        super(MicroManagerSingleImageStack, self).__init__(image_path=image_path, **kwargs)

    @staticmethod
    def has_valid_format(path: str):
        """check whether this is an image stack with the naming format from micromanager"""
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

        path = pathlib.Path(self.image_path)
        fname_stat = path.stat()
        fcreated = datetime.fromtimestamp(fname_stat.st_atime).strftime('%a %b/%d/%Y, %H:%M:%S')
        fmodified = datetime.fromtimestamp(fname_stat.st_mtime).strftime('%a %b/%d/%Y, %H:%M:%S')

        self._info = self.images_md.copy()
        self._info['folder'] = pathlib.Path(self.image_path).parent,
        self._info['filename'] = path.name,
        self._info['change (Unix), creation (Windows)'] = fcreated
        self._info['most recent modification'] = fmodified

        self._info = pd.DataFrame(self._info)
        return self._info

    def _image(self, plane, row=0, col=0, fid=0) -> MetadataImage:
        t, c, z = re.search(r'^FrameKey-([0-9]*)-([0-9]*)-([0-9]*)$', plane).groups()
        t, c, z = int(t), int(c), int(z)

        key = f"c{c:0{len(str(self.n_channels))}d}z{z:0{len(str(self.n_zstacks))}d}t{t:0{len(str(self.n_frames))}d}"
        ix = self.all_planes_md_dict[key]

        filename = self.files[ix]
        im_path = self.image_path.parent / filename

        if os.path.exists(im_path):
            with tf.TiffFile(im_path) as tif:
                if ix < len(tif.pages):
                    image = tif.pages[ix].asarray()
                    t_int = self.timestamps[t] - self.timestamps[t - 1] if t > 0 else self.timestamps[t]
                    return MetadataImage(reader='MicroManagerStack',
                                         image=image,
                                         pix_per_um=self.pix_per_um, um_per_pix=self.um_per_pix,
                                         time_interval=t_int,
                                         timestamp=self.timestamps[t],
                                         frame=t, channel=c, z=z, width=self.width, height=self.height,
                                         intensity_range=[np.min(image), np.max(image)])
                else:
                    self.log.error(f'Frame, channel, z ({t},{c},{z}) not found in file.')
                    raise FrameNotFoundError
        else:
            self.log.error(f'Frame, channel, z ({t},{c},{z}) not found in file.')
            raise FrameNotFoundError
