from pathlib import Path
from typing import Union, List, Dict, Set

import pandas as pd

from fileops.image.imagemeta import MetadataImage


class ImageFileBase:
    image_path: Union[None, Path]
    base_path: Union[None, Path]
    render_path: Union[None, Path]
    metadata_path: Union[None, Path]
    all_series: Union[None, Set] = None
    instrument_md: Union[None, Set] = None
    objectives_md: Union[None, Set] = None

    md: Union[None, Dict] = None
    images_md: Union[None, Dict] = None
    planes_md: Union[None, Dict] = None
    all_planes: Union[None, List] = None  # TODO: need to deprecate
    all_planes_md_dict: Union[None, Dict] = None

    timestamps: Union[None, List] = None  # list of all timestamps recorded in the experiment
    time_interval: float = 0  # average time difference between frames in seconds
    positions: Union[None, Set] = None  # set of different XY positions on the stage that the acquisition took
    channels: Union[None, Set] = None  # set of channels that the acquisition took
    zstacks: Union[None, List] = None  # list of focal planes acquired
    zstacks_um: Union[None, List] = None  # list of focal planes acquired in micrometers
    frames: Union[None, List] = None  # list of timepoints recorded
    files: Union[None, List] = None  # list of filenames that the measurement extends to
    n_positions: int = 0
    n_channels: int = 0
    n_zstacks: int = 0
    n_frames: int = 0
    _md_n_channels: int = 0
    _md_n_zstacks: int = 0
    _md_n_frames: int = 0
    magnification: int = 1  # integer storing the magnitude of the lens
    um_per_pix: float = 1  # calibration assuming square pixels
    pix_per_um: float = 1  # calibration assuming square pixels
    um_per_z: float = 1  # distance step of z axis
    width: int = 0
    height: int = 0

    @staticmethod
    def has_valid_format(path: Path):
        raise NotImplementedError

    @property
    def info(self) -> pd.DataFrame:
        return pd.DataFrame()

    @property
    def series(self):
        raise NotImplementedError

    @series.setter
    def series(self, s):
        self._load_imageseries()

    def _load_imageseries(self):
        pass

    def _image(self, plane, row=0, col=0, fid=0) -> MetadataImage:
        raise NotImplementedError

    def _get_metadata(self):
        pass
