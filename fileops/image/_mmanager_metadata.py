import json
import re
from logging import Logger

import numpy as np
import tifffile as tf

from fileops.image._base import ImageFileBase


class MetadataVersion10Mixin(ImageFileBase):
    log: Logger

    def __init__(self, **kwargs):
        base_name = self.image_path.name.split(".ome")[0]

        self._meta_name = f"{base_name}_metadata.txt"
        self.metadata_path = self.image_path.parent / self._meta_name
        self._load_metadata()

        super().__init__(**kwargs)

    def _load_metadata(self):
        try:
            with open(self.metadata_path) as f:
                self.md = json.load(f)
                summary = self.md['Summary']
        except FileNotFoundError:
            summary = {
                "ChNames":        None,
                "StagePositions": None,
                "Width":          -1,
                "Height":         -1,
                "Slices":         -1,
                "Frames":         -1,
                "Channels":       -1,
                "Positions":      -1,
                "z-step_um":      np.NaN,
            }

        with tf.TiffFile(self.image_path) as tif:
            imagej_metadata = tif.imagej_metadata
            if imagej_metadata is not None and "Info" in imagej_metadata:
                # get rid of any comments in the beginning of the file that are not JSON compliant
                info_str = re.sub(r'^(.|\n)*?\{', '{', imagej_metadata["Info"])
                imagej_metadata["Info"] = json.loads(info_str)
            micromanager_metadata = tif.micromanager_metadata
            keyframe = tif.pages.keyframe

        if 'StagePositions' in summary:
            self.all_positions = summary["StagePositions"]

        self.channel_names = summary["ChNames"]
        self.channels = set(range(summary["Channels"])) if "Channels" in summary else {}

        mmf_size_x = int(getattr(summary, "Width", -1))
        mmf_size_y = int(getattr(summary, "Height", -1))
        mmf_size_z = int(getattr(summary, "Slices", -1))
        mmf_size_t = int(getattr(summary, "Frames", -1))
        mmf_size_c = int(getattr(summary, "Channels", -1))
        mmf_physical_size_z = float(summary["z-step_um"]) if "z-step_um" in summary else np.NaN

        mm_sum = micromanager_metadata["Summary"]
        mm_size_x = int(getattr(mm_sum, "Width", -1))
        mm_size_y = int(getattr(mm_sum, "Height", -1))
        mm_size_z = int(getattr(mm_sum, "Slices", -1))
        mm_size_t = int(getattr(mm_sum, "Frames", -1))
        mm_size_c = int(getattr(mm_sum, "Channels", -1))
        mm_size_p = int(getattr(mm_sum, "Positions", -1))
        mm_physical_size_z = float(getattr(mm_sum, "z-step_um", np.NaN))

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

        self.pix_per_um = 1. / res
        self.um_per_pix = res
        self.um_per_z = max(mmf_physical_size_z, mm_physical_size_z)
        self.width = max(mmf_size_x, mm_size_x, kf_size_x, keyframe.imagewidth)
        self.height = max(mmf_size_y, mm_size_y, kf_size_y, keyframe.imagelength)
        self._md_n_zstacks = max(mmf_size_z, mm_size_z)
        self._md_n_frames = max(mmf_size_t, mm_size_t)
        self._md_n_channels = max(mmf_size_c, mm_size_c, len(self.channels))

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
                    self.timestamps.append(int(getattr(self.md[fkey], "ElapsedTime-ms", -1)) / 1000)
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

        # check consistency of stored number of frames vs originally recorded in the metadata
        n_frames = len(self.frames)
        if self._md_n_frames == n_frames:
            self.n_frames = self._md_n_frames
        else:
            self.log.warning(
                f"Inconsistency detected while counting number of frames, "
                f"will use counted ({n_frames}) instead of reported ({self._md_n_frames}).")
            self.n_frames = n_frames

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
        delta_t_mm = int(getattr(mm_sum, "Interval_ms", -1))
        delta_t_im = int(getattr(imagej_metadata["Info"], "Interval_ms", -1)) if imagej_metadata else -1
        self.time_interval = max(float(delta_t_mm), float(delta_t_im)) / 1000

        # retrieve the position of which the current file is associated to
        if "Position" in micromanager_metadata["IndexMap"]:
            self.positions = set(micromanager_metadata["IndexMap"]["Position"])
            self.n_positions = len(self.positions)
        elif "StagePositions" in mm_sum:
            self.positions = positions
            self.n_positions = len(positions)
        else:
            self.positions = None
            self.n_positions = mm_size_p

        self._dtype = np.uint16
