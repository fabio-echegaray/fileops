import os
import os
import pathlib
import re
from datetime import datetime

import numpy as np
import pandas as pd
import tifffile as tf
from scipy.stats import stats

from fileops.image._ome import ome_info, _get_metadata_from_ome_string
from fileops.image.exceptions import FrameNotFoundError
from fileops.image.image_file import ImageFile
from fileops.image.imagemeta import MetadataImage
from fileops.logger import get_logger


class MicroManagerSingleImageStack(ImageFile):
    log = get_logger(name='MicroManagerImageStack')

    def __init__(self, image_path: str = None, failover_dt=1, **kwargs):
        # check whether this is a folder with images and take the folder they are in as position
        if not self.has_valid_format(image_path):
            raise FileNotFoundError("Format is not correct.")

        img_file = os.path.basename(image_path)
        super().__init__(image_path=image_path, failover_dt=failover_dt, **kwargs)

        # obtain metadata
        if os.path.exists(image_path):
            with tf.TiffFile(image_path) as tif:
                if hasattr(tif, "ome_metadata") and tif.ome_metadata:
                    self.images_md = ome_info(_get_metadata_from_ome_string(tif.ome_metadata),
                                              ome_ns={'ome': 'http://www.openmicroscopy.org/Schemas/OME/2016-06'})

        self._load_imageseries()

    @staticmethod
    def has_valid_format(path: str):
        """check whether this is an image stack with the naming format from micromanager"""
        with tf.TiffFile(path) as tif:
            if not hasattr(tif, "ome_metadata") or not tif.ome_metadata:
                return False
            if not hasattr(tif, "micromanager_metadata") or not tif.micromanager_metadata:
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
        return self._info

    def _load_imageseries(self):
        if self.images_md is None:
            return

        self.channels = self.images_md["channels"]
        self.um_per_z = self.images_md["pixel_size"][2]
        self.zstacks = sorted(np.unique([int(p["TheZ"]) for p in self.images_md["planes"]]))
        self.zstacks_um = sorted(np.unique([float(p["PositionZ"]) for p in self.images_md["planes"]]))
        self.frames = sorted(np.unique([int(p["TheT"]) for p in self.images_md["planes"]]))

        self.n_channels = self.images_md["n_channels"]
        self.n_zstacks = len(self.zstacks)
        self.n_frames = self.images_md["frames"]

        p = pd.DataFrame(self.images_md["planes"])
        p["DeltaT"] = pd.to_numeric(p["DeltaT"])
        self.timestamps = p.groupby("TheT")["DeltaT"].min()

        mag_str = self.images_md["magnification"]
        if mag_str is not None:
            mag_rgx = re.search(r"(?P<mag>[0-9]+)x", mag_str)
            self.magnification = int(mag_rgx.groupdict()['mag'])

        for td in self.images_md["tiff_data"]:
            # build dictionary where the keys are combinations of c z t and values are the index
            self.all_planes_md_dict[f"c{int(td['FirstC']):0{len(str(self.n_channels))}d}"
                                    f"z{int(td['FirstZ']):0{len(str(self.n_zstacks))}d}"
                                    f"t{int(td['FirstT']):0{len(str(self.n_frames))}d}"] = int(td['IFD'])
            self.all_planes.append(td)

        self.time_interval = stats.mode(np.diff(self.timestamps))

        # load width and height information from tiff metadata
        self.width = self.images_md["width"]
        self.height = self.images_md["height"]
        # assuming square pixels, extract X component
        res = self.images_md["pixel_size"][0]
        self.pix_per_um = res
        self.um_per_pix = 1. / res

        self.log.info(f"{len(self.frames)} frames and {len(self.all_planes_md_dict)} image planes in total.")
        super()._load_imageseries()

    def ix_at(self, c, z, t):
        czt_str = f"c{c:0{len(str(self.n_channels))}d}z{z:0{len(str(self.n_zstacks))}d}t{t:0{len(str(self.n_frames))}d}"
        if czt_str in self.all_planes_md_dict:
            return self.all_planes_md_dict[czt_str]
        self.log.warning(f"No index found for c={c}, z={z}, and t={t}.")

    def _image(self, plane, row=0, col=0, fid=0) -> MetadataImage:
        t, c, z, ix = int(plane["FirstT"]), int(plane["FirstC"]), int(plane["FirstZ"]), int(plane["IFD"])

        if os.path.exists(self.image_path):
            with tf.TiffFile(self.image_path) as tif:
                if ix <= len(tif.pages):
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
                    self.log.error(f'Frame {t} not found in file.')
                    raise FrameNotFoundError
        else:
            self.log.error(f'Frame {t} not found in file.')
            raise FrameNotFoundError
