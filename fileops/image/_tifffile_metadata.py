import itertools
import json
import os
import re
from logging import Logger
from pathlib import Path
from typing import List

import numpy as np
import tifffile as tf

from fileops.image._base import ImageFileBase


def _find_associated_files(path, prefix) -> List[Path]:
    out = list()
    for root, directories, filenames in os.walk(path):
        for file in filenames:
            if len(file) > len(prefix):
                if file[:len(prefix)] == prefix:
                    out.append(file)
    return out


class MetadataOMETifffileMixin(ImageFileBase):
    log: Logger

    def __init__(self, **kwargs):
        self.error_loading_metadata = False
        self._tif = None
        self._load_metadata()

        super().__init__(**kwargs)

    def _load_metadata(self):
        self._tif = tf.TiffFile(self.image_path)
        imagej_metadata = self._tif.imagej_metadata
        if imagej_metadata is not None and "Info" in imagej_metadata:
            # get rid of any comments in the beginning of the file that are not JSON compliant
            info_str = re.sub(r'^(.|\n)*?\{', '{', imagej_metadata["Info"])
            imagej_metadata["Info"] = json.loads(info_str)
            if "Prefix" in imagej_metadata["Info"]:
                self.files.extend(_find_associated_files(self.base_path, imagej_metadata["Info"]["Prefix"]))
        micromanager_metadata = self._tif.micromanager_metadata
        keyframe = self._tif.pages.keyframe

        mm_sum = micromanager_metadata["Summary"]

        self._md_channels = set(range(mm_sum["Channels"])) if "Channels" in mm_sum else {}
        self._md_channel_names = mm_sum["ChNames"]

        mm_size_x = int(mm_sum.get("Width", -1))
        mm_size_y = int(mm_sum.get("Height", -1))
        mm_size_z = int(mm_sum.get("Slices", -1))
        mm_size_t = int(mm_sum.get("Frames", -1))
        mm_size_c = int(mm_sum.get("Channels", -1))
        mm_size_p = int(mm_sum.get("Positions", -1))
        mm_physical_size_z = float(mm_sum.get("z-step_um", np.nan))

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
        self.um_per_z = max(mm_physical_size_z, -1)
        self.width = max(mm_size_x, kf_size_x, keyframe.imagewidth)
        self.height = max(mm_size_y, kf_size_y, keyframe.imagelength)
        self._md_n_zstacks = max(mm_size_z, -1)
        self._md_n_frames = max(mm_size_t, -1)
        self._md_n_channels = max(mm_size_c, -1)
        self._md_deltaT_ms = int(mm_sum.get("Interval_ms", -1e6))

        # build a list of the images stored in sequence
        positions = set()
        if "IntendedDimensions" in mm_sum:
            ax_dim = mm_sum["IntendedDimensions"]
        else:
            ax_dim = reversed(mm_sum["AxisOrder"])

        ax_ord = list(reversed([a for a in mm_sum["AxisOrder"] if a in ax_dim.keys()]))
        for counter, key_pos in enumerate(itertools.product(*[range(ax_dim[a]) for a in ax_ord if a in ax_dim.keys()])):
            p = key_pos[ax_ord.index("position")] if "position" in ax_ord else 0
            c = key_pos[ax_ord.index("channel")] if "channel" in ax_ord else 0
            t = key_pos[ax_ord.index("time")] if "time" in ax_ord else 0
            z = key_pos[ax_ord.index("z")] if "z" in ax_ord else 0
            if z == 0 and c == 0:
                self.timestamps.append(self._md_deltaT_ms * t / 1000)
            self.channels.add(c)
            self.zstacks.append(z)
            self.zstacks_um.append(self.um_per_z * z)
            self.frames.append(t)

            positions.add(p)

            # build dictionary where the keys are combinations of c z t and values are the index
            key = (f"c{c:0{len(str(ax_dim['channel']))}d}"
                   f"z{z:0{len(str(ax_dim['z']))}d}"
                   f"t{t:0{len(str(ax_dim['time']))}d}")
            self.all_planes.append(key)
            if key in self.all_planes_md_dict:
                # raise KeyError("Keys should not repeat!")
                self.log.error(f"Keys should not repeat! ({key})")
            else:
                # print(f"{fkey} - {key} gets {counter}")
                self.all_planes_md_dict[key] = (counter, c, z, t)

        self.timestamps = sorted(np.unique(self.timestamps))
        self.frames = sorted(np.unique(self.frames))
        self.zstacks = sorted(np.unique(self.zstacks))
        self.zstacks_um = sorted(np.unique(self.zstacks_um))

        # check consistency of stored number of frames vs originally recorded in the metadata
        n_frames = len(self.frames)
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
        else:
            self.log.warning(
                f"Inconsistency detected while counting number of channels, "
                f"will use counted ({n_channels}) instead of reported ({self._md_n_channels}).")
            self.n_channels = n_channels

        # check consistency of stored number of z-stacks vs originally recorded in the metadata
        n_stacks = len(self.zstacks)
        if self._md_n_zstacks == n_stacks:
            self.n_zstacks = self._md_n_zstacks
        else:
            self.log.warning(
                f"Inconsistency detected while counting number of z-stacks, "
                f"will use counted ({n_stacks}) instead of reported ({self._md_n_zstacks}).")
            self.n_zstacks = n_stacks

        # retrieve or estimate sampling period
        delta_t_mm = int(mm_sum.get("Interval_ms", -1))
        delta_t_im = int(imagej_metadata["Info"].get("Interval_ms", -1)) if imagej_metadata else -1
        self.time_interval = max(float(delta_t_mm), float(delta_t_im)) / 1000

        # retrieve the position of which the current file is associated to
        if "Position" in micromanager_metadata["IndexMap"]:
            self.positions = set(micromanager_metadata["IndexMap"]["Position"])
            self.all_positions = self.positions
            self.n_positions = len(self.positions)
        elif mm_sum["Positions"] == 1:
            self.positions = {"DefaultPlaceholder0"}
            self.n_positions = 1
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
            raise IndexError("Number of positions could not be extracted")

        self._dtype = np.uint16
