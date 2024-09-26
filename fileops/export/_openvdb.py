from pathlib import Path

import numpy as np

from fileops.export import bioformats_to_tiffseries
from fileops.export._vtk_state import save_vtk_python_state
from fileops.export.config import ExportConfig
from fileops.logger import get_logger
from fileops.pathutils import ensure_dir

log = get_logger(name='export-openvdb')


def export_paraview(cfg: ExportConfig, out_path: Path, until_frame=np.inf):
    log.info(f"Exporting data from configuration file {cfg.path} into Paraview format")

    red_trans_fn = "[0, 0.0, 0.0, 0.0, 12000, 1.0, 0.0, 0.0]"
    grn_trans_fn = "[0, 0.0, 0.0, 0.0, 12000, 0.0, 1.0, 0.0]"
    blu_trans_fn = "[0, 0.0, 0.0, 0.0, 12000, 0.0, 0.0, 1.0]"
    tfn_lst = [red_trans_fn, grn_trans_fn, blu_trans_fn]

    channels = dict()
    export_tiff_path = ensure_dir(out_path / "tiff")

    vol_timeseries, ch_metadata = bioformats_to_tiffseries(cfg_struct=cfg, save_path=export_tiff_path,
                                                           until_frame=until_frame)
    dtype_max = np.iinfo(np.uint16).max
    for chkey, tr_fn in zip(ch_metadata.keys(), tfn_lst):
        ch = int(chkey[2:])
        channels[chkey] = {
            "label":               f"ch{ch:01d}",
            # mind the folder structure to get these names right
            "position":            cfg.image_file.image_path.name.split("_")[-1].split(".")[0],
            "session":             cfg.image_file.image_path.parent.parent.name,
            "tiff_files_list":     str(ch_metadata[chkey]["files"]),
            "ctf_rgb_points":      tr_fn,
            "otf_opacity_points":  "[0,    0.000, 0.5, 0.0, "
                                   "2000,  0.000, 0.5, 0.0, "
                                   "6500,  0.030, 0.5, 0.0, "
                                   "9300,  0.200, 0.5, 0.0, "
                                   "13000, 0.200, 0.5, 0.0]",
            "scale_transfer_fn":   "[0, 0.0, 0.5, 0.0, 11670, 1.0, 0.5, 0.0]",
            "opacity_transfer_fn": "[0, 0.0, 0.5, 0.0, 11670, 1.0, 0.5, 0.0]",
            "exp_corr_params":     ch_metadata[chkey]["photobleach_params"],
            "mean":                ch_metadata[chkey]["mean"],
            "minmax":              ch_metadata[chkey]["minmax"],
            "min":                 np.min([mm[0] for mm in ch_metadata[chkey]["minmax"]]),
            "max":                 np.max([mm[1] for mm in ch_metadata[chkey]["minmax"]]),
            "dtype_max":           dtype_max
        }
    save_vtk_python_state(out_path / f"paraview_state.py", channel_info=channels)
