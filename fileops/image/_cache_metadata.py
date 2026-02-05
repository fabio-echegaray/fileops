import gzip
import json

import numpy as np


def save_metadata_to_disk(imf):
    md_path = imf.image_path.parent / f"{imf.image_path.name}.fileops.metadata.safe_to_delete.txt.gz"
    with gzip.open(md_path, "wt") as f:
        md_dict = {
            "pix_per_um":         imf.pix_per_um,
            "um_per_pix":         imf.um_per_pix,
            "um_per_z":           imf.um_per_z,
            "width":              imf.width,
            "height":             imf.height,
            "n_frames":           imf.n_frames,
            "n_channels":         imf.n_channels,
            "n_zstacks":          imf.n_zstacks,
            "n_positions":        imf.n_positions,
            "frames":             imf.frames,
            "timestamps":         imf.timestamps,
            "channels":           imf.channels,
            "zstacks":            imf.zstacks,
            "zstacks_um":         imf.zstacks_um,
            "positions":          imf.positions,
            "all_planes":         imf.all_planes,
            "all_planes_md_dict": imf.all_planes_md_dict,
            "time_interval":      imf.time_interval,
            "all_series":         imf.all_series,
            # "all_positions":     imf.all_positions,
            "_md_n_positions":    imf._md_n_positions,
            "_md_n_zstacks":      imf._md_n_zstacks,
            "_md_n_frames":       imf._md_n_frames,
            "_md_n_channels":     imf._md_n_channels,
            # "_md_deltaT_ms":      imf._md_deltaT_ms,
            "_md_timestamps":     imf._md_timestamps,
            "_md_frames":         imf._md_frames,
            "_md_zstacks":        imf._md_zstacks,
            "_counted_frames":    imf._counted_frames,
            "_counted_channels":  imf._counted_channels,
            "_counted_zstacks":   imf._counted_zstacks,
            "_md_dt":             imf._md_dt,
            "_dtype":             imf._dtype,
        }
        json.dump(md_dict, f, cls=NumpyEncoder)
        imf.log.info(f"Compiled metadata of file {imf.image_path.name} saved to disk.")


def load_metadata_from_disk(imf) -> bool:
    md_path = imf.image_path.parent / f"{imf.image_path.name}.fileops.metadata.safe_to_delete.txt.gz"
    if md_path.exists():
        with gzip.open(md_path, "rt") as f:
            try:
                md_dict = json.load(f)

                imf.pix_per_um = md_dict['pix_per_um']
                imf.um_per_pix = md_dict['um_per_pix']
                imf.um_per_z = md_dict['um_per_z']
                imf.width = md_dict['width']
                imf.height = md_dict['height']
                imf.n_frames = md_dict['n_frames']
                imf.n_channels = md_dict['n_channels']
                imf.n_zstacks = md_dict['n_zstacks']
                imf.n_positions = md_dict['n_positions']
                imf.frames = md_dict['frames']
                imf.timestamps = md_dict['timestamps']
                imf.channels = set(md_dict['channels'])
                imf.zstacks = md_dict['zstacks']
                imf.zstacks_um = md_dict['zstacks_um']
                imf.time_interval = md_dict['time_interval']
                imf.positions = set(md_dict['positions'])
                imf.all_planes = md_dict['all_planes']
                imf.all_planes_md_dict = md_dict['all_planes_md_dict']
                imf.all_series = md_dict['all_series']
                # imf.all_positions = md_dict['all_positions']
                imf._md_n_positions = md_dict['_md_n_positions']
                imf._md_n_zstacks = md_dict['_md_n_zstacks']
                imf._md_n_frames = md_dict['_md_n_frames']
                imf._md_n_channels = md_dict['_md_n_channels']
                # imf._md_deltaT_ms = md_dict['_md_deltaT_ms']
                imf._md_timestamps = md_dict['_md_timestamps']
                imf._md_frames = md_dict['_md_frames']
                imf._md_zstacks = md_dict['_md_zstacks']
                imf._counted_frames = md_dict['_counted_frames']
                imf._counted_channels = md_dict['_counted_channels']
                imf._counted_zstacks = md_dict['_counted_zstacks']
                imf._md_dt = md_dict['_md_dt']
                imf._dtype = md_dict['_dtype']

                return True
            except Exception as e:
                print(e)
                return False
    return False


class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, set):
            return list(obj)
        if isinstance(obj, type):
            return str(obj)
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.bool_):
            return bool(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        return super(NumpyEncoder, self).default(obj)
