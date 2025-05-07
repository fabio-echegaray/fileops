import json
import os
import re
from datetime import datetime
from json import JSONDecodeError
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


class MicroMagellanPositionImageStack(ImageFile):
    log = get_logger(name='MicroMagellanPositionImageStack')

    def __init__(self, image_path: Path = None, failover_dt=1, **kwargs):
        # check whether this is a folder with images and take the folder they are in as position
        if not self.has_valid_format(image_path):
            raise FileNotFoundError("Format is not correct.")

        img_file = os.path.basename(image_path)
        image_series = int(re.match(r'.*Pos([0-9]*).*', img_file).group(1))
        if 'image_series' in kwargs:
            kwargs.pop('image_series')

        super().__init__(image_path=image_path, image_series=image_series, failover_dt=failover_dt, **kwargs)

        self.metadata_path = Path(image_path) / f'{img_file[:-8]}_metadata.txt'

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
        self._load_imageseries()

    @staticmethod
    def has_valid_format(path: Path):
        """check whether this is an image stack with the naming format from micromanager"""
        folder = os.path.dirname(path)
        return bool(re.match(r'.*_MMStack_Pos[0-9]\..*', path.name)) and not folder_is_micromagellan(folder)

    @property
    def info(self) -> pd.DataFrame:
        if self._info is not None:
            return self._info

        path = Path(self.image_path)
        fname_stat = path.stat()
        fcreated = datetime.fromisoformat(self.md['Summary']['StartTime'][:-10]).strftime('%a %b/%d/%Y, %H:%M:%S')
        fmodified = datetime.fromtimestamp(fname_stat.st_mtime).strftime('%a %b/%d/%Y, %H:%M:%S')
        key = f'FrameKey-0-0-0'
        series_info = list()
        if key in self.md:
            meta = self.md[key]

            size_x = size_y = size_z = float(meta['PixelSizeUm'])
            size_inv = 1 / size_x if size_x > 0 else None
            size_x_unit = size_y_unit = size_z_unit = 'µm'
            series_info = [{
                'folder':                            Path(self.image_path).parent,
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

        super(MicroMagellanPositionImageStack, self.__class__).series.fset(self, s)

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
                self.all_planes_md_dict[f"c{int(c):0{len(str(self._md_n_channels))}d}"
                                        f"z{int(z):0{len(str(self._md_n_zstacks))}d}"
                                        f"t{int(t):0{len(str(self._md_n_frames))}d}"] = counter
                counter += 1

        self.time_interval = getattr(stats.mode(np.diff(self.timestamps), axis=None), "mode")

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
        if "FileName" in self.md[plane]:
            file = self.md[plane]["FileName"]
        else:
            self.log.error(f'Frame {t} not found in file.')
            raise FrameNotFoundError

        path = os.path.join(os.path.dirname(self.image_path), file)
        if os.path.exists(path):
            with tf.TiffFile(path) as tif:
                if t <= len(tif.pages):
                    image = tif.pages[t].asarray()
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
