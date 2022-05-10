import json
import os
import pathlib
import re
from datetime import datetime
from json import JSONDecodeError
from typing import List

import numpy as np
import pandas as pd
from scipy.stats import stats

from fileops.image.image_file import ImageFile
from fileops.image.imagemeta import MetadataImageSeries, MetadataImage
from fileops.logger import get_logger

import tifffile as tf


def folder_is_micromagellan(path: str) -> bool:
    # get to a path level that contains sub-folders
    p = pathlib.Path(path)
    keep_exploring = True
    while keep_exploring:
        folders = [x for x in p.iterdir() if x.is_dir()]
        keep_exploring = p.parent != p.root and not folders
        p = p.parent
    key_full_res = [f for f in folders if 'Full resolution' in f.name]
    if key_full_res:
        folders.pop(folders.index(key_full_res[0]))
        key_folders = [np.any([f'Downsampled_x{2 ** i:d}' in f.name for i in range(1, 12)]) for f in folders]
        return np.all(key_folders)
    else:
        return False


class MicroManagerFolderSeries(ImageFile):
    log = get_logger(name='MicroManagerFolderSeries')

    def __init__(self, image_path: str = None, **kwargs):
        super().__init__(image_path=image_path, **kwargs)

        # check whether this is a folder with images and take the folder they are in as position
        if not self.has_valid_format(image_path):
            raise FileNotFoundError("Format is not correct.")
        if os.path.isdir(image_path):
            self.base_path = image_path
            image_path = os.path.join(image_path, 'img_channel000_position000_time000000000_z000.tif')
        else:
            self.base_path = os.path.dirname(image_path)

        pos_fld = pathlib.Path(image_path).parent.name
        # image_series = int(re.search(r'Pos([0-9]*)', pos_fld).group(1))

        self.metadata_path = os.path.join(self.base_path, 'metadata.txt')

        with open(self.metadata_path) as f:
            self.md = json.load(f)

        self.all_positions = self.md['Summary']['StagePositions']
        self._load_imageseries()

    @staticmethod
    def has_valid_format(path: str):
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

        path = pathlib.Path(self.image_path)
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

        super(MicroManagerFolderSeries, self.__class__).series.fset(self, s)

    def _load_imageseries(self):
        if not self.md:
            return

        all_positions = list(set([s.split('/')[0].split('-')[1] for s in self.md.keys() if s[:8] == 'Metadata']))

        self.channels = self.md["Summary"]["ChNames"]
        self.um_per_z = self.md["Summary"]["z-step_um"]

        pos = int(all_positions[self._series][-1])
        self.image_path = os.path.join(self.base_path, f'img_channel000_position{pos:03d}_time000000000_z000.tif')

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
                self.all_planes_md_dict[f"{int(c):0{len(str(self.n_channels))}d}"
                                        f"{int(z):0{len(str(self.n_zstacks))}d}"
                                        f"{int(t):0{len(str(self.n_frames))}d}"] = counter
                w.add(self.md[key]["Width"])
                h.add(self.md[key]["Height"])
                if f"Pos{p}" not in pos_set:
                    pos_set.add(f"Pos{p}")
                counter += 1

        self.time_interval = stats.mode(np.diff(self.timestamps))
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

    def _image(self, plane, row=0, col=0, fid=0) -> MetadataImage:  # PLANE HAS THE NAME OF THE FILE OF THE IMAGE PLANE
        c, p, t, z = re.search(r'img_channel([0-9]*)_position([0-9]*)_time([0-9]*)_z([0-9]*).tif$', plane).groups()
        c, p, t, z = int(c), int(p), int(t), int(z)
        # load file from folder
        fname = os.path.join(self.base_path, plane)
        if os.path.exists(fname):
            with tf.TiffFile(fname) as tif:
                image = tif.pages[0].asarray()
            return MetadataImage(image=image,
                                 pix_per_um=self.pix_per_um, um_per_pix=self.um_per_pix,
                                 time_interval=None,
                                 timestamp=self.timestamps[t],
                                 frame=t, channel=c, z=z, width=self.width, height=self.height,
                                 intensity_range=[np.min(image), np.max(image)])
        else:
            self.log.error(f'File of frame {t} not found in folder.')
            return MetadataImage(image=None,
                                 pix_per_um=np.nan, um_per_pix=np.nan,
                                 time_interval=np.nan,
                                 timestamp=self.timestamps[t],
                                 frame=t, channel=c, z=z, width=self.width, height=self.height,
                                 intensity_range=[np.nan])


class MicroManagerImageStack(ImageFile):
    log = get_logger(name='MicroManagerImageStack')

    def __init__(self, image_path: str = None, failover_dt=1, **kwargs):
        # check whether this is a folder with images and take the folder they are in as position
        if not self.has_valid_format(image_path):
            raise FileNotFoundError("Format is not correct.")

        img_file = os.path.basename(image_path)
        image_series = int(re.match(r'.*Pos([0-9]*).*', img_file).group(1))
        if 'image_series' in kwargs:
            kwargs.pop('image_series')

        self.metadata_path = os.path.join(os.path.dirname(image_path), f'{img_file[:-8]}_metadata.txt')

        with open(self.metadata_path) as f:
            json_str = f.readlines()

            try:
                self.md = json.loads("".join(json_str))
            except JSONDecodeError as e:
                json_str[-2] = json_str[-2][:-2] + "\n"
                terminator = [] if json_str[-2].find(":") > 0 else ["]\n"]
                json_str = json_str[:-1] + terminator + ["}\n"] + ["}\n"]
                # json_str = json_str[:-1]
                print(json_str[-5:])
                self.md = json.loads("".join(json_str))

        self.all_positions = [f'Pos{image_series}']

        super().__init__(image_path=image_path, image_series=image_series, failover_dt=failover_dt, **kwargs)

    @staticmethod
    def has_valid_format(path: str):
        """check whether this is an image stack with the naming format from micromanager"""
        folder = os.path.dirname(path)
        return bool(re.match(r'.*_MMStack_Pos[0-9]\..*', path)) and not folder_is_micromagellan(folder)

    @property
    def info(self) -> pd.DataFrame:
        if self._info is not None:
            return self._info

        path = pathlib.Path(self.image_path)
        fname_stat = path.stat()
        fcreated = datetime.fromisoformat(self.md['Summary']['StartTime'][:-10]).strftime('%a %b/%d/%Y, %H:%M:%S')
        fmodified = datetime.fromtimestamp(fname_stat.st_mtime).strftime('%a %b/%d/%Y, %H:%M:%S')
        key = f'FrameKey-0-0-0'
        if key in self.md:
            meta = self.md[key]

            size_x = size_y = size_z = float(meta['PixelSizeUm'])
            size_inv = 1 / size_x if size_x > 0 else None
            size_x_unit = size_y_unit = size_z_unit = 'µm'
            series_info = [{
                'folder':                            pathlib.Path(self.image_path).parent,
                'filename':                          meta['FileName'],
                'image_id':                          meta['UUID'],
                'image_name':                        meta['FileName'],
                'instrument_id':                     '',
                'pixels_id':                         '',
                'channels':                          int(self.md['Summary']['Channels']),
                'z-stacks':                          int(self.md['Summary']['Slices']),
                'frames':                            int(self.md['Summary']['Frames']),
                'position':                          self._series,
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
            }]

            self._info = pd.DataFrame(series_info)
            return self._info

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

        super(MicroManagerImageStack, self.__class__).series.fset(self, s)

    def _load_imageseries(self):
        if not self.md:
            return

        all_positions = [p["Label"] for p in self.md["Summary"]["StagePositions"]]

        self.channels = self.md["Summary"]["ChNames"]
        self.um_per_z = self.md["Summary"]["z-step_um"]

        pos = int(all_positions[self._series][-1])
        frkey = f"FrameKey-0-0-0"
        if frkey not in self.md:
            raise FileNotFoundError(f"Couldn't find data for position {pos}.")

        mag_str = self.md[frkey]["TINosePiece-Label"]
        mag_rgx = re.search(r"(?P<mag>[0-9]+)x", mag_str)
        self.magnification = int(mag_rgx.groupdict()['mag'])

        counter = 0
        for key in self.md:
            if key[0:8] == "FrameKey":
                t, c, z = re.search(r'^FrameKey-([0-9]*)-([0-9]*)-([0-9]*)$', key).groups()
                t, c, z = int(t), int(c), int(z)

                fname = self.md[key]["FileName"] if "FileName" in self.md[key] else ""
                fname = fname.split("/")[1] if "/" in fname else fname
                self.files.append(fname)
                self.timestamps.append(self.md[key]["ElapsedTime-ms"] / 1000)
                self.zstacks.append(self.md[key]["ZPositionUm"])
                self.frames.append(int(t))
                self.all_planes.append(key)
                # build dictionary where the keys are combinations of c z t and values are the index
                self.all_planes_md_dict[f"c{int(c):0{len(str(self.n_channels))}d}"
                                        f"z{int(z):0{len(str(self.n_zstacks))}d}"
                                        f"t{int(t):0{len(str(self.n_frames))}d}"] = counter
                counter += 1

        self.time_interval = stats.mode(np.diff(self.timestamps))

        # load width and height information from tiff metadata
        file = self.md[frkey]["FileName"]
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

        self.position_md = self.md["Summary"]["StagePositions"][self._series]

        self.log.info(f"{len(self.frames)} frames and {counter} image planes in total.")
        super()._load_imageseries()

    def ix_at(self, c, z, t):
        czt_str = f"c{c:0{len(str(self.n_channels))}d}z{z:0{len(str(self.n_zstacks))}d}t{t:0{len(str(self.n_frames))}d}"
        if czt_str in self.all_planes_md_dict:
            return self.all_planes_md_dict[czt_str]
        self.log.warning(f"No index found for c={c}, z={z}, and t={t}.")

    def _image(self, plane, row=0, col=0, fid=0) -> MetadataImage:  # PLANE HAS THE NAME OF THE FILE OF THE IMAGE PLANE
        t, c, z = re.search(r'^FrameKey-([0-9]*)-([0-9]*)-([0-9]*)$', plane).groups()
        t, c, z = int(t), int(c), int(z)

        # load file from folder
        file = self.md[plane]["FileName"]
        path = os.path.join(os.path.dirname(self.image_path), file)
        if os.path.exists(path):
            with tf.TiffFile(path) as tif:
                if t <= len(tif.pages):
                    image = tif.pages[t].asarray()
                    t_int = self.timestamps[t] - self.timestamps[t - 1] if t > 0 else self.timestamps[t]
                    return MetadataImage(image=image,
                                         pix_per_um=self.pix_per_um, um_per_pix=self.um_per_pix,
                                         time_interval=t_int,
                                         timestamp=self.timestamps[t],
                                         frame=t, channel=c, z=z, width=self.width, height=self.height,
                                         intensity_range=[np.min(image), np.max(image)])
                else:
                    self.log.error(f'Frame {t} not found in file.')
                    return MetadataImage(image=None,
                                         pix_per_um=np.nan, um_per_pix=np.nan,
                                         time_interval=np.nan,
                                         timestamp=self.timestamps[t],
                                         frame=t, channel=c, z=z, width=self.width, height=self.height,
                                         intensity_range=[np.nan])
