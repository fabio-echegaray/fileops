from pathlib import Path
from typing import Union, List, Dict, Set, Protocol

import pandas as pd

from fileops.image.imagemeta import MetadataImage


class ImageFileBase(Protocol):
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

    timestamps: Union[None, List] = None  # list of timestamps (see _md_timestamps for the list extracted from file)
    time_interval: float = 0  # average time difference between frames in seconds
    positions: Union[None, Set] = None  # set of different XY positions on the stage that the acquisition took
    channels: Union[None, Set] = None  # set of channels that the acquisition took
    zstacks: Union[None, List] = None  # list of focal planes (see _md_zstacks for the list extracted from file)
    zstacks_um: Union[None, List] = None  # list of focal planes acquired in micrometers
    frames: Union[None, List] = None  # list of timepoints recorded
    files: Union[None, List] = None  # list of filenames that the measurement extends to
    n_positions: int = 0
    n_channels: int = 0
    n_zstacks: int = 0
    n_frames: int = 0
    magnification: int = 1  # integer storing the magnification of the lens
    um_per_pix: float = 1.  # calibration assuming square pixels
    pix_per_um: float = 1.  # calibration assuming square pixels
    um_per_z: float = 1.  # distance step of z axis
    width: int = 0
    height: int = 0

    # internal state of the different image readers
    _series: int = 0

    # attributes when metadata is acquired from reading the file or when it's overridden
    _md_dt: float = None
    _override_dt: float = None
    _md_timestamps: Union[None, List] = None  # list of all timestamps recorded in the experiment
    _md_zstacks: Union[None, List] = None  # list of focal planes acquired in the experiment
    _override_pix_um: int = None  # override pixel size in microns
    _counted_positions: int = None
    _counted_frames: int = None
    _counted_channels: int = None
    _counted_zstacks: int = None
    _md_n_positions: int = None
    _md_n_frames: int = None
    _md_n_channels: int = None
    _md_n_zstacks: int = None
    _md_pixel_datatype: Union[int, str] = None

    @staticmethod
    def has_valid_format(path: Path):
        raise NotImplementedError

    @property
    def info(self) -> pd.DataFrame:
        return pd.DataFrame()

    @property
    def series(self) -> int | str | dict:
        raise NotImplementedError

    @series.setter
    def series(self, s: int):
        self._load_imageseries(s)

    def _load_imageseries(self, series: int):
        raise NotImplementedError

    def _image(self, plane, row=0, col=0, fid=0) -> MetadataImage:
        raise NotImplementedError

    def _get_metadata(self):
        pass
