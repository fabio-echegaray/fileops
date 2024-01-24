import os
from pathlib import Path

import numpy as np
import pandas as pd

from fileops.image.image_file import ImageFile
from fileops.image.imagemeta import MetadataImage
from fileops.loaders import load_tiff
from fileops.logger import get_logger


class ImageJImageFile(ImageFile):
    log = get_logger(name='ImageJ')

    def __init__(self, image_path: Path = None, **kwargs):
        super().__init__(image_path=image_path, **kwargs)

        # check whether this is a folder with images and take the folder they are in as position
        # if not self.has_valid_format(image_path):
        #     raise FileNotFoundError("Format is not correct.")
        if os.path.isdir(image_path):
            self.base_path = image_path
            self.image_path = image_path / 'img_channel000_position000_time000000000_z000.tif'
        else:
            self.base_path = image_path.parent

        self.md = self.md_xml = None

        self.all_planes_md_dict = {}

        self._images = []
        self._nimgs = 0
        self._load_imageseries()

    @property
    def info(self) -> pd.DataFrame:
        raise NotImplementedError

    def _load_imageseries(self):
        tiff_series = load_tiff(self.image_path)

        self._images = tiff_series.images

        self.n_channels = tiff_series.channels
        self.n_zstacks = tiff_series.zstacks
        self.n_frames = tiff_series.frames
        self._md_n_zstacks = self.n_zstacks
        self._md_n_frames = self.n_frames
        self._md_n_channels = self.n_channels

        self.channels = set(range(tiff_series.channels))

        self.magnification = 1

        self.um_per_pix = tiff_series.um_per_pix
        self.pix_per_um = tiff_series.pix_per_um
        self.um_per_z = tiff_series.um_per_z

        self.timestamps = tiff_series.timestamps
        self.zstacks = list(range(tiff_series.zstacks))
        self.frames = list(range(tiff_series.frames))
        self.time_interval = tiff_series.time_interval
        self.width = tiff_series.width
        self.height = tiff_series.height

        self._nimgs = tiff_series.channels * tiff_series.frames * tiff_series.zstacks

        counter = 0
        for c in self.channels:
            for z in self.zstacks:
                for t in self.frames:
                    self.all_planes_md_dict[f"{int(c):0{len(str(self._md_n_channels))}d}"
                                            f"{int(z):0{len(str(self._md_n_zstacks))}d}"
                                            f"{int(t):0{len(str(self._md_n_frames))}d}"] = counter
                    self.all_planes.append({"c": c, "t": t, "z": z})
                    counter += 1

        self.log.info(f"ImageJ tiff file loaded. "
                      f"Image size (WxH)=({self.width:d}x{self.height:d}); "
                      f"calibration is {self.pix_per_um:0.3f} pix/um and {self.um_per_z:0.3f} um/z-step; "
                      f"movie has {self.n_frames} frames, {self.n_channels} channels, {self.n_zstacks} z-stacks and "
                      f"{self._nimgs} image planes in total.")
        super()._load_imageseries()

    def _image(self, plane, **kwargs) -> MetadataImage:
        self.log.debug(f"Retrieving image of index={plane}")

        image = self._images[plane["t"], plane["z"], plane["c"], :, :]
        return MetadataImage(reader='ImageJImageFile',
                             image=image,
                             pix_per_um=self.pix_per_um, um_per_pix=self.um_per_pix,
                             time_interval=None,
                             timestamp=self.timestamps[plane["t"]],
                             frame=plane["t"], channel=plane["c"], z=plane["z"], width=self.width, height=self.height,
                             intensity_range=[np.min(image), np.max(image)])
