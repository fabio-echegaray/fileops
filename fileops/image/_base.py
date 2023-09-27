from pathlib import Path
from typing import Union, List, Dict, Set

import pandas as pd

from fileops.image.imagemeta import MetadataImage


class ImageFileBase:
    image_path: Union[None, Path]
    base_path: Union[None, Path]
    render_path: Union[None, Path]
    metadata_path: Union[None, Path]
    all_series: Set = set()
    instrument_md: Set = set()
    objectives_md: Set = set()

    md: Dict = dict()
    images_md: Dict = dict()
    planes_md: Dict = dict()
    all_planes: List = list()
    all_planes_md_dict: Dict = dict()

    timestamps: List = list()  # list of all timestamps recorded in the experiment
    time_interval: float = 0  # average time difference between frames
    channels: Set = set()  # list of channels that the acquisition took
    zstacks: List = list()  # list of focal planes acquired
    zstacks_um: List = list()  # list of focal planes acquired in micrometers
    frames: List = list()  # list of timepoints recorded
    files: List = list()  # list of filenames that the measurement extends to
    n_channels: int = 0
    n_zstacks: int = 0
    n_frames: int = 0
    magnification: int = 1  # integer storing the magnitude of the lens
    um_per_pix: float = 1  # calibration assuming square pixels
    pix_per_um: float = 1  # calibration assuming square pixels
    um_per_z: float  # distance step of z axis
    width: int = 0
    height: int = 0
    all_planes_md_dict: Dict

    @staticmethod
    def has_valid_format(path: Path):
        pass

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
