import json
import os
import pathlib
import re
from datetime import datetime
from typing import List

import numpy as np
import pandas as pd
from scipy.stats import stats

from fileops.image import to_8bit
from fileops.image.imagemeta import MetadataImageSeries, MetadataImage
from fileops.logger import get_logger

import tifffile as tf


class MicroManagerFolderSeries:
    log = get_logger(name='MicroManagerFolderSeries')

    def __init__(self, image_path: str, failover_dt=1, **kwargs):
        self.image_path = os.path.abspath(image_path)
        self.base_path = os.path.dirname(self.image_path)
        # self.cache_path = os.path.join(self.base_path, '_cache')
        # self.render_path = os.path.join(self.cache_path, 'out', 'render')
        self.log.debug(f"Image file path is {self.image_path.encode('ascii')}.")

        self.metadata_path = os.path.join(self.image_path, 'metadata.txt')

        with open(self.metadata_path) as f:
            self.md = json.load(f)

        # check whether this is a folder with images and take the folder they are in as position
        if self.has_valid_format(image_path):  # folder is full of tif files
            pos_fld = os.path.basename(image_path)
            self._series = int(pos_fld[-1])

        self.all_positions = []
        self.instrument_md = []
        self.objectives_md = []

        self.position_md = None
        # self.planes_md = None
        self.all_planes = []

        self.timestamps = []  # list of all timestamps recorded in the experiment
        self.time_interval = None  # average time difference between frames
        self.channels = []  # list of channels that the acquisition took
        self.zstacks = []  # list of focal planes acquired
        self.frames = []  # list of timepoints recorded
        self.files = []  # list of filenames that the measurement extends to
        self.n_channels = 0
        self.n_zstacks = 0
        self.n_frames = 0
        self.magnification = None  # integer storing the magnitude of the lens
        self.um_per_pix = None  # calibration assuming square pixels
        self.pix_per_um = None  # calibration assuming square pixels
        self.um_per_z = None  # distance step of z axis
        self.width = None
        self.height = None
        self.n_frames = 0
        self.n_channels = 0
        self.n_zstacks = 0
        self.all_planes_md_dict = {}
        self._load_imageseries_folder()

        if not self.timestamps:
            self.time_interval = failover_dt
            self.timestamps = [failover_dt * f for f in self.frames]

        # super(CachedImageFile, self).__init__(**kwargs)

    @staticmethod
    def has_valid_format(path: str):
        """check whether this is a folder with images and take the folder they are in as position"""
        files = os.listdir(path)
        cnt = np.bincount([f[-3:] == 'tif' for f in files])
        return cnt[1] / (np.sum(cnt)) > .9  # check folder is full of tif files

    @property
    def info(self) -> pd.DataFrame:
        fname_stat = pathlib.Path(self.image_path).stat()
        fcreated = datetime.fromisoformat(self.md['Summary']['StartTime'][:-10]).strftime('%a %b/%d/%Y, %H:%M:%S')
        fmodified = datetime.fromtimestamp(fname_stat.st_mtime).strftime('%a %b/%d/%Y, %H:%M:%S')
        series_info = list()
        for pos in self.all_positions:  # iterate through all positions
            p = int(pos['Label'][-1])
            key = f'Metadata-Pos{p}/img_channel000_position00{p}_time000000000_z000.tif'
            if key in self.md:
                meta = self.md[key]

                size_x = size_y = size_z = float(meta['PixelSizeUm'])
                size_inv = 1 / size_x if size_x > 0 else None
                size_x_unit = size_y_unit = size_z_unit = 'µm'
                series_info.append({
                    'folder':                            self.image_path,
                    'filename':                          f'img_channel000_position00{p}_time000000000_z000.tif',
                    'image_id':                          meta['UUID'],
                    'image_name':                        os.path.basename(self.image_path),
                    'instrument_id':                     '',
                    'pixels_id':                         '',
                    'channels':                          int(self.md['Summary']['Channels']),
                    'z-stacks':                          int(self.md['Summary']['Slices']),
                    'frames':                            int(self.md['Summary']['Frames']),
                    'position':                          p,
                    'delta_t':                           float(meta["ElapsedTime-ms"]),
                    'width':                             self.width,
                    'height':                            self.height,
                    'data_type':                         self.md['Summary']['PixelType'],
                    'objective_id':                      meta["TINosePiece-Label"],
                    'magnification':                     int(
                        re.search(r' ([0-9]*)x', meta["TINosePiece-Label"]).group(1)),
                    'pixel_size':                        (size_x, size_y, size_z),
                    'pixel_size_unit':                   (size_x_unit, size_y_unit, size_z_unit),
                    'pix_per_um':                        (size_inv, size_inv, size_inv),
                    'change (Unix), creation (Windows)': fcreated,
                    'most recent modification':          fmodified,
                })
        out = pd.DataFrame(series_info)
        return out

    @property
    def series(self):
        return self.all_positions[self._series]

    @series.setter
    def series(self, s):
        if type(s) == int:
            self._series = s
        elif type(s) == str and s[:3] == 'Pos':
            self._series = int(s[3:])
        elif type(s) == dict and 'Label' in s:
            self._series = int(s['Label'][3:])
        else:
            raise ValueError("Unexpected type of variable to load series.")

        self._load_imageseries_folder()

    def _load_imageseries_folder(self):
        self.all_positions = []
        all_positions = [p["Label"] for p in self.md["Summary"]["StagePositions"]]

        self.channels = self.md["Summary"]["ChNames"]
        self.um_per_z = self.md["Summary"]["z-step_um"]

        pos = int(all_positions[self._series][-1])
        frkey = f"Metadata-Pos{pos}/img_channel000_position00{pos}_time000000000_z000.tif"
        if frkey not in self.md:
            raise FileNotFoundError(f"Couldn't find data for position {pos}.")

        self.magnification = self.md[frkey]["TINosePiece-Label"]
        self.um_per_pix = self.md[frkey]["PixelSizeUm"]
        self.pix_per_um = 1 / self.um_per_pix if self.um_per_pix > 0 else None

        counter = 0
        w = set()
        h = set()
        pos_set = set()
        for key in self.md:
            if key[0:8] == "Metadata":
                c, p, t, z = re.search(r'img_channel([0-9]*)_position([0-9]*)_time([0-9]*)_z([0-9]*).tif$',
                                       key).groups()
                c, p, t, z = int(c), int(p), int(t), int(z)
                # if int(pos) == self._series:
                self.files.append(self.md[key]["FileName"])
                self.timestamps.append(self.md[key]["ElapsedTime-ms"])
                self.zstacks.append(self.md[key]["ZPositionUm"])
                self.frames.append(int(t))
                self.all_planes.append(key[14:])
                # build dictionary where the keys are combinations of c z t and values are the index
                self.all_planes_md_dict[f"{int(c):0{len(str(self.n_channels))}d}"
                                        f"{int(z):0{len(str(self.n_zstacks))}d}"
                                        f"{int(t):0{len(str(self.n_frames))}d}"] = counter
                w.add(self.md[key]["Width"])
                h.add(self.md[key]["Height"])
                if f"Pos{p}" not in pos_set:
                    pos_set.add(f"Pos{p}")
                    self.all_positions.extend(
                        [pos for pos in self.md["Summary"]["StagePositions"] if pos["Label"] == f"Pos{p}"])
                counter += 1

        self.time_interval = stats.mode(np.diff(self.timestamps))
        self.width = w.pop() if len(w) == 1 else None
        self.height = h.pop() if len(h) == 1 else None
        self.position_md = self.md["Summary"]["StagePositions"][self._series]

        self.log.info(f"{len(self.frames)} frames and {counter} image planes in total.")

    def ix_at(self, c, z, t):
        czt_str = f"{c:0{len(str(self.n_channels))}d}{z:0{len(str(self.n_zstacks))}d}{t:0{len(str(self.n_frames))}d}"
        if czt_str in self.all_planes_md_dict:
            return self.all_planes_md_dict[czt_str]
        self.log.warning(f"No index found for c={c}, z={z}, and t={t}.")

    def image(self, *args) -> MetadataImage:
        if len(args) == 1 and isinstance(args[0], int):
            ix = args[0]
            plane = self.all_planes[ix]
            return self._image(plane, row=0, col=0, fid=0)

    def images(self, channel=0, zstack=0, as_8bit=False) -> List[np.ndarray]:
        for t in sorted(self.frames):
            ix = self.ix_at(c=channel, z=zstack, t=t)
            plane = self.all_planes[ix]
            img = self._image(plane, row=0, col=0, fid=0).image
            if as_8bit:
                img = img / img.max() * 255  # normalizes data in range 0 - 255
                yield img.astype(np.uint8)
            else:
                yield img

    def image_series(self, channel='all', zstack='all', frame='all', as_8bit=False) -> MetadataImageSeries:
        images = list()
        frames = self.frames if frame == 'all' else [frame]
        zstacks = self.zstacks if zstack == 'all' else [zstack]
        channels = self.channels if channel == 'all' else [channel]

        for t in frames:
            for zs in zstacks:
                for ch in channels:
                    ix = self.ix_at(ch, zs, t)
                    plane = self.all_planes[ix]
                    img = self._image(plane).image
                    images.append(to_8bit(img) if as_8bit else img)
        images = np.asarray(images).reshape((len(frames), len(zstacks), len(channels), *images[-1].shape))
        return MetadataImageSeries(images=images, pix_per_um=self.pix_per_um, um_per_pix=self.um_per_pix,
                                   frames=len(frames), timestamps=len(frames),
                                   time_interval=None,  # self.time_interval,
                                   channels=len(channels), zstacks=len(zstacks),
                                   width=self.width, height=self.height,
                                   series=None, intensity_ranges=None)

    def _image(self, plane, row=0, col=0, fid=0) -> MetadataImage:  # PLANE HAS THE NAME OF THE FILE OF THE IMAGE PLANE
        c, p, t, z = re.search(r'img_channel([0-9]*)_position([0-9]*)_time([0-9]*)_z([0-9]*).tif$', plane).groups()
        c, p, t, z = int(c), int(p), int(t), int(z)
        # load file from folder
        fname = os.path.join(self.image_path, plane)
        if os.path.exists(fname):
            self.log.debug(f"Loading image {fname} from cache.")
            with tf.TiffFile(fname) as tif:
                image = tif.pages[0].asarray()
                return MetadataImage(image=image,
                                     pix_per_um=self.pix_per_um, um_per_pix=self.um_per_pix,
                                     time_interval=None,
                                     timestamp=self.timestamps[t],
                                     frame=t, channel=c, z=z, width=self.width, height=self.height,
                                     intensity_range=[np.min(image), np.max(image)])
