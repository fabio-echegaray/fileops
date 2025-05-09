import json
import os
import re
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import tifffile as tf
from scipy.stats import stats

from fileops.image._mmagellan import folder_is_micromagellan
from fileops.image.exceptions import FrameNotFoundError
from fileops.image.image_file import ImageFile
from fileops.image.imagemeta import MetadataImage
from fileops.logger import get_logger


class MicroManagerFolderSeries(ImageFile):
    log = get_logger(name='MicroManagerFolderSeries')

    def __init__(self, image_path: Path = None, **kwargs):
        super().__init__(image_path=image_path, **kwargs)

        # check whether this is a folder with images and take the folder they are in as position
        if not self.has_valid_format(image_path):
            raise FileNotFoundError("Format is not correct.")
        if os.path.isdir(image_path):
            self.base_path = image_path
            # get first file
            fname = os.listdir(image_path)[0]
            self.image_path = image_path / fname
        else:
            self.base_path = image_path.parent

        # pos_fld = image_path.parent.name
        # image_series = int(re.search(r'Pos([0-9]*)', pos_fld).group(1))

        self.metadata_path = self.base_path / 'metadata.txt'

        with open(self.metadata_path) as f:
            self.md = json.load(f)

        self.all_positions = self.md['Summary']['StagePositions']
        self._load_imageseries()

    @staticmethod
    def has_valid_format(path: Path):
        """check whether this is a folder with images and take the folder they are in as position"""
        if os.path.isdir(path):
            folder = path
        else:
            folder = os.path.dirname(path)
        if folder_is_micromagellan(folder):
            return False
        files = os.listdir(folder)
        cnt = np.bincount([f[-3:] == 'tif' for f in files])
        # check folder is full of tif files and metadata file is inside folder
        return cnt[1] / (np.sum(cnt)) > .99 and os.path.exists(os.path.join(folder, 'metadata.txt'))

    @property
    def info(self) -> pd.DataFrame:
        if self._info is not None:
            return self._info

        path = self.image_path
        fname_stat = path.stat()
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
                    'folder':                            self.base_path,
                    'filename':                          f'img_channel000_position00{p}_time000000000_z000.tif',
                    'image_id':                          meta['UUID'],
                    'image_name':                        path.parent.name,
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

        self._info = pd.DataFrame(series_info)
        return self._info

    @property
    def series(self):
        if len(self.all_series) == 0:
            return 0
        else:
            __series = sorted(self.all_series)
            return __series[self._series]

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

        super(MicroManagerFolderSeries, self.__class__).series.fset(self, s)

    def _load_imageseries(self):
        if not self.md:
            return

        all_positions = list(set([s.split('/')[0].split('-')[1] for s in self.md.keys() if s[:8] == 'Metadata']))

        self.channels = self.md["Summary"]["ChNames"]
        self.um_per_z = self.md["Summary"]["z-step_um"]

        assert len(all_positions) == 1, "only single position stacks are currently allowed"
        pos = int(all_positions[0][-1])
        self.image_path = self.base_path / f'img_channel000_position{pos:03d}_time000000000_z000.tif'

        frkey = f"Metadata-Pos{pos}/img_channel000_position{pos:03d}_time000000000_z000.tif"
        if frkey not in self.md:
            raise FileNotFoundError(f"Couldn't find data for position {pos}.")

        mag_str = self.md[frkey]["TINosePiece-Label"]
        mag_rgx = re.search(r"(?P<mag>[0-9]+)x", mag_str)
        self.magnification = int(mag_rgx.groupdict()['mag'])

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
                self.files.append(self.md[key]["FileName"].split("/")[1])
                self.timestamps.append(self.md[key]["ElapsedTime-ms"] / 1000)
                self.zstacks.append(self.md[key]["ZPositionUm"])
                self.frames.append(int(t))
                self.all_planes.append(key[14:])
                # build dictionary where the keys are combinations of c z t and values are the index
                self.all_planes_md_dict[f"c{int(c):0{len(str(self._md_n_channels))}d}"
                                        f"z{int(z):0{len(str(self._md_n_zstacks))}d}"
                                        f"t{int(t):0{len(str(self._md_n_frames))}d}"] = counter
                w.add(self.md[key]["Width"])
                h.add(self.md[key]["Height"])
                if f"Pos{p}" not in pos_set:
                    pos_set.add(f"Pos{p}")
                counter += 1

        self.time_interval = getattr(stats.mode(np.diff(self.timestamps), axis=None), "mode")
        self.width = w.pop() if len(w) == 1 else None
        self.height = h.pop() if len(h) == 1 else None
        self.position_md = self.md["Summary"]["StagePositions"][self._series]

        # load and update width, height and resolution information from tiff metadata in case it exists
        file = self.md[frkey]["FileName"].split('/')[1]
        path = os.path.join(os.path.dirname(self.image_path), file)
        with tf.TiffFile(path) as tif:
            if tif.is_micromanager:
                summary = tif.micromanager_metadata["Summary"]
                self.width = summary["Width"]
                self.height = summary["Height"]
                # assuming square pixels, extract X component
                if 'XResolution' in tif.pages[0].tags:
                    xr = tif.pages[0].tags['XResolution'].value
                    res = float(xr[0]) / float(xr[1])  # pixels per um
                    if tif.pages[0].tags['ResolutionUnit'].value == tf.TIFF.RESUNIT.CENTIMETER:
                        res = res / 1e4
                    self.pix_per_um = res
                    self.um_per_pix = 1. / res

        self.log.info(f"{len(self.frames)} frames and {counter} image planes in total.")
        super()._load_imageseries()

    def _image(self, plane, row=0, col=0, fid=0) -> MetadataImage:
        if re.search(r'^*_Z([0-9]*)_C([0-9]*)_T([0-9]*).ome.tif$', plane) is not None:
            z, c, t = re.search(r'^*_Z([0-9]*)_C([0-9]*)_T([0-9]*).ome.tif$', plane).groups()
            z, c, t = int(z), int(c), int(t)
        elif re.search(r'img_channel([0-9]*)_position([0-9]*)_time([0-9]*)_z([0-9]*).tif$', plane) is not None:
            c, p, t, z = re.search(r'img_channel([0-9]*)_position([0-9]*)_time([0-9]*)_z([0-9]*).tif$', plane).groups()
            c, p, t, z = int(c), int(p), int(t), int(z)
        else:
            raise FrameNotFoundError

        # load file from folder
        fname = os.path.join(self.base_path, plane)
        if os.path.exists(fname):
            with tf.TiffFile(fname) as tif:
                image = tif.pages[0].asarray()
            return MetadataImage(reader='MicroManagerFolder',
                                 image=image,
                                 pix_per_um=self.pix_per_um, um_per_pix=self.um_per_pix,
                                 time_interval=None,
                                 timestamp=self.timestamps[t],
                                 frame=t, channel=c, z=z, width=self.width, height=self.height,
                                 intensity_range=[np.min(image), np.max(image)])
        else:
            self.log.error(f'File of frame {t} not found in folder.')
            raise FrameNotFoundError
