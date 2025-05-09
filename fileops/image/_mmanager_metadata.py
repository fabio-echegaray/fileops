import itertools
import json
import numpy as np
import os
import re
import tifffile as tf
from logging import Logger
from pathlib import Path
from typing import List, Dict

from fileops.image._base import ImageFileBase
from fileops.pathutils import find


def _find_associated_files(path, prefix) -> List[Path]:
    out = list()
    for root, directories, filenames in os.walk(path):
        for file in filenames:
            if len(file) > len(prefix):
                ext = file.split('.')[-1]
                if file[:len(prefix)] == prefix and ext in ['tif', 'tiff']:
                    out.append(file)
    return out


def mm_metadata_files(search_path: Path, image_path: Path) -> List[str]:
    base_name = image_path.name.split(".ome")[0]
    if base_name[-2:] == "_1":
        base_name = base_name[:-2]
    md_names = [f"{base_name}_metadata.txt", f"{base_name[:-2]}_metadata.txt"]
    mm_meta_files = find(f"*metadata*.txt", search_path)
    meta_names = [p.name for p in mm_meta_files]

    return [md_name for n in meta_names for md_name in md_names if md_name == n]


class MetadataVersion10Mixin(ImageFileBase):
    log: Logger
    frames_per_file: Dict

    def __init__(self, **kwargs):
        m_names_match = mm_metadata_files(self.image_path.parent, self.image_path)
        if len(m_names_match) == 1:
            self._meta_name = m_names_match[0]
        elif np.sum(m_names_match) > 1:
            raise FileExistsError("too many metadata files found in folder")
        else:
            raise FileNotFoundError(f"could not find metadata file for image {self.image_path.name}")

        self.metadata_path = self.image_path.parent / self._meta_name
        self.error_loading_metadata = False
        self._load_metadata()

        self.frames_per_file = dict()

        super().__init__(**kwargs)

    def _load_metadata(self):
        try:
            with open(self.metadata_path) as f:
                self.md = json.load(f)
                summary = self.md['Summary']
        except FileNotFoundError:
            self.error_loading_metadata = True
            summary = {
                "ChNames":        None,
                "StagePositions": None,
                "Width":          -1,
                "Height":         -1,
                "Slices":         -1,
                "Frames":         -1,
                "Channels":       -1,
                "Positions":      -1,
                "z-step_um":      np.nan,
            }

        with tf.TiffFile(self.image_path) as tif:
            imagej_metadata = tif.imagej_metadata
            if imagej_metadata is not None and "Info" in imagej_metadata:
                # get rid of any comments in the beginning of the file that are not JSON compliant
                info_str = re.sub(r'^(.|\n)*?\{', '{', imagej_metadata["Info"])
                imagej_metadata["Info"] = json.loads(info_str)
                if "Prefix" in imagej_metadata["Info"]:
                    self.files.extend(_find_associated_files(self.base_path, imagej_metadata["Info"]["Prefix"]))
            micromanager_metadata = tif.micromanager_metadata
            keyframe = tif.pages.keyframe

        self._md_channel_names = summary["ChNames"]
        self._md_channels = set(range(summary["Channels"])) if "Channels" in summary else {}

        mmf_size_x = int(summary.get("Width", -1))
        mmf_size_y = int(summary.get("Height", -1))
        mmf_size_z = int(summary.get("Slices", -1))
        mmf_size_t = int(summary.get("Frames", -1))
        mmf_size_c = int(summary.get("Channels", -1))
        mmf_physical_size_z = float(summary.get("z-step_um", np.NaN))

        mm_sum = micromanager_metadata["Summary"]
        mm_size_x = int(mm_sum.get("Width", -1))
        mm_size_y = int(mm_sum.get("Height", -1))
        mm_size_z = int(mm_sum.get("Slices", -1))
        mm_size_t = int(mm_sum.get("Frames", -1))
        mm_size_c = int(mm_sum.get("Channels", -1))
        mm_size_p = int(mm_sum.get("Positions", -1))
        mm_physical_size_z = float(mm_sum.get("z-step_um", np.NaN))

        kf_size_x = int(keyframe.shape[keyframe.axes.find('X')])
        kf_size_y = int(keyframe.shape[keyframe.axes.find('Y')])

        # calculate pixel size assuming square pixels
        if 'XResolution' in keyframe.tags:
            xr = keyframe.tags['XResolution'].value
            res = float(xr[0]) / float(xr[1])  # pixels per um
            if keyframe.tags['ResolutionUnit'].value == tf.TIFF.RESUNIT.CENTIMETER:
                res = res / 1e4
        else:
            res = 1

        # magnification = None
        # size_x_unit = size_y_unit = size_z_unit = "um"

        self.pix_per_um = res
        self.um_per_pix = 1. / res
        self.um_per_z = max(mmf_physical_size_z, mm_physical_size_z)
        self.width = max(mmf_size_x, mm_size_x, kf_size_x, keyframe.imagewidth)
        self.height = max(mmf_size_y, mm_size_y, kf_size_y, keyframe.imagelength)
        self._md_n_zstacks = max(mmf_size_z, mm_size_z)
        self._md_n_frames = max(mmf_size_t, mm_size_t)
        self._md_n_channels = max(mmf_size_c, mm_size_c)

        # build a list of the images stored in sequence
        positions = set()
        for counter, fkey in enumerate(list(self.md.keys())[1:]):
            if fkey[0:8] == "FrameKey":
                t, c, z = re.search(r'^FrameKey-([0-9]*)-([0-9]*)-([0-9]*)$', fkey).groups()
                t, c, z = int(t), int(c), int(z)

                positions.add(self.md[fkey]["PositionName"])
                fname = self.md[fkey]["FileName"] if "FileName" in self.md[fkey] else ""
                fname = fname.split("/")[1] if "/" in fname else fname
                self.files.append(fname)
                if z == 0 and c == 0:
                    self.timestamps.append(int(self.md[fkey].get("ElapsedTime-ms", -1e6)) / 1000)
                self.channels.add(c)
                self.zstacks.append(z)
                self.zstacks_um.append(self.md[fkey]["ZPositionUm"])
                self.frames.append(t)
                # build dictionary where the keys are combinations of c z t and values are the index
                key = (f"c{c:0{len(str(self._md_n_channels))}d}"
                       f"z{z:0{len(str(self._md_n_zstacks))}d}"
                       f"t{t:0{len(str(self._md_n_frames))}d}")
                self.all_planes.append(key)
                if key in self.all_planes_md_dict:
                    # raise KeyError("Keys should not repeat!")
                    print(f"Keys should not repeat! ({key})")
                else:
                    # print(f"{fkey} - {key} gets {counter}")
                    self.all_planes_md_dict[key] = counter

        self.timestamps = sorted(np.unique(self.timestamps))
        self.frames = sorted(np.unique(self.frames))
        self.zstacks = sorted(np.unique(self.zstacks))
        self.zstacks_um = sorted(np.unique(self.zstacks_um))

        # count stored images
        unq_files = np.unique(self.files)
        n_idx = 0
        for f in unq_files:
            with tf.TiffFile(self.image_path.parent / f) as tif:
                self.frames_per_file[f] = len(tif.pages)
                n_idx += len(tif.pages)
        last_recorded_image_idx = self.all_planes[n_idx - 1]
        rgx = re.search(r'^c([0-9]*)z([0-9]*)t([0-9]*)$', last_recorded_image_idx)
        last_c, last_z, last_t = rgx.groups()

        # check consistency of stored number of frames vs originally recorded in the metadata
        n_frames = int(last_t)
        if self._md_n_frames == n_frames:
            self.n_frames = self._md_n_frames
        elif self.error_loading_metadata:
            self.log.info(
                f"Metadata file was not found, so will be using reported N of frames ({self._md_n_frames}).")
            self.n_frames = self._md_n_frames
            self.frames = [f for f in range(self.n_frames)]
        else:
            self.log.warning(
                f"Inconsistency detected while counting number of frames, "
                f"will use counted ({n_frames}) instead of reported ({self._md_n_frames}).")
            self.n_frames = n_frames

        # check consistency of stored number of channels vs originally recorded in the metadata
        n_channels = len(self.channels)
        if self._md_n_channels == n_channels:
            self.n_channels = self._md_n_channels
        elif self.error_loading_metadata:
            self.log.info(
                f"Metadata file was not found, so will be using reported N of channels ({self._md_n_channels}).")
            self.n_channels = self._md_n_channels
            self.channels = set([c for c in range(self.n_channels)])
        else:
            self.log.warning(
                f"Inconsistency detected while counting number of channels, "
                f"will use counted ({n_channels}) instead of reported ({self._md_n_channels}).")
            self.n_channels = n_channels

        # check consistency of stored number of z-stacks vs originally recorded in the metadata
        n_stacks = len(self.zstacks)
        if self._md_n_zstacks == n_stacks:
            self.n_zstacks = self._md_n_zstacks
        elif self.error_loading_metadata:
            self.log.info(
                f"Metadata file was not found, so will be using reported N of z-stacks ({self._md_n_zstacks}).")
            self.n_zstacks = self._md_n_zstacks
            self.zstacks = [z for z in range(self.n_zstacks)]
        else:
            self.log.warning(
                f"Inconsistency detected while counting number of z-stacks, "
                f"will use counted ({n_stacks}) instead of reported ({self._md_n_zstacks}).")
            self.n_zstacks = n_stacks

        # retrieve or estimate sampling period
        delta_t_mm = int(mm_sum.get("Interval_ms", -1))
        delta_t_im = int(imagej_metadata["Info"].get("Interval_ms", -1)) if imagej_metadata else -1
        self.time_interval = max(float(delta_t_mm), float(delta_t_im)) / 1000

        if self.error_loading_metadata:
            for counter, fkey in enumerate(itertools.product(self.frames, self.channels, self.zstacks)):
                t, c, z = fkey
                t, c, z = int(t), int(c), int(z)

                # build dictionary where the keys are combinations of c z t and values are the index
                key = (f"c{c:0{len(str(self._md_n_channels))}d}"
                       f"z{z:0{len(str(self._md_n_zstacks))}d}"
                       f"t{t:0{len(str(self._md_n_frames))}d}")
                self.all_planes.append(key)
                self.all_planes_md_dict[key] = counter

            self.timestamps = [self.time_interval * f for f in self.frames]

        # retrieve the position of which the current file is associated to
        if "Position" in micromanager_metadata["IndexMap"]:
            self.positions = set(micromanager_metadata["IndexMap"]["Position"])
            self.all_positions = self.positions
            self.n_positions = len(self.positions)
        elif "StagePositions" in mm_sum:
            mm_positions = mm_sum.get("StagePositions", ["DefaultPlaceholder0"])
            self.all_positions = mm_positions
            if len(mm_positions) == 0:
                self.positions = {"DefaultPlaceholder0"}
            elif len(mm_positions) > 1:
                # the number of reported positions is because of the metadata reporting all positions instead of
                # the file having all the positions encoded in it
                self.positions = positions
            self.n_positions = len(positions)
        else:
            self.positions = positions
            self.all_positions = self.positions
            if len(self.positions) == 0:
                self.positions = {"DefaultPlaceholder0"}
            self.n_positions = len(self.positions)

        self._dtype = np.uint16
