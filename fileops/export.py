from pathlib import Path
from typing import Union

import javabridge
import numpy as np
from matplotlib import pyplot as plt

from fileops.cached.cached_image_file import ensure_dir
from fileops.export import bioformats_to_tiffseries
from fileops.export._vtk_state import save_vtk_python_state
from fileops.export.config import read_config, search_config_files
from fileops.logger import get_logger

log = get_logger(name='export')


# ------------------------------------------------------------------------------------------------------------------
#  routines for plotting pixel intensity
# ------------------------------------------------------------------------------------------------------------------
def plot_intensity_histogram(img_vol: np.ndarray, filename: Union[Path, str] = "histogram.pdf"):
    # determine the number of columns
    n_frames, n_zstacks, width, height = img_vol.shape

    fig = plt.figure(figsize=(10, 10))
    ax = fig.add_subplot(projection="3d")

    # get and plot histograms
    for j, fr in enumerate(range(n_frames)):
        histvals, edges = np.histogram(img_vol[fr, :, :, :].flatten(), bins=50)

        # plot the histogram as a bar for each bin
        xcenter = np.convolve(edges, np.ones(2), "valid") / 2
        xwidth = np.diff(edges)
        ax.bar(left=xcenter, height=histvals, width=xwidth, zs=j, zdir="y", color="b", alpha=0.05)

    ax.set_xlabel("bin")
    ax.set_ylabel("frame")
    ax.set_zlabel("value")

    fig.savefig(filename, dpi=300)


def _test_shape():
    vol = np.ones(shape=(100, 100, 100), dtype=np.uint8)
    vol[10:20, 10:20, 10:20] = 30
    vol[20:40, 20:40, 20:40] = 70
    vol[40:50, 40:50, 40:50] = 150
    vol[80:90, 80:90, 80:90] = 240

    return vol


if __name__ == "__main__":
    # base_path = Path("/home/lab/Documents/Fabio/Blender/Timepoints from ROI")
    cfg_path_list = search_config_files(Path("/media/lab/Data/Fabio/export/Sas6-01/"))
    # [
    # Path("/home/lab/Documents/Fabio/Blender/20230317 Early division from Anand/export_definition.cfg"),
    # base_path / "fig-1a" / "export_definition-00.cfg",
    # base_path / "fig-1a" / "export_definition-08.cfg",
    # base_path / "fig-1a" / "export_definition-12.cfg",
    # base_path / "fig-1a" / "export_definition-18.cfg",
    # base_path / "fig-1a" / "export_definition-22.cfg",
    # base_path / "fig-1a" / "export_definition-28.cfg",
    # base_path / "fig-1a" / "export_definition-32.cfg",
    #
    # base_path / "fig-1b" / "export_definition-00.cfg",
    # base_path / "fig-1b" / "export_definition-08.cfg",
    # base_path / "fig-1b" / "export_definition-16.cfg",
    # base_path / "fig-1b" / "export_definition-22.cfg",
    # base_path / "fig-1b" / "export_definition-24.cfg",
    # base_path / "fig-1b" / "export_definition-31.cfg",
    # base_path / "fig-1b" / "export_definition-33.cfg",
    #
    # base_path / "fig-1c" / "export_definition-00.cfg",
    # base_path / "fig-1c" / "export_definition-06.cfg",
    # base_path / "fig-1c" / "export_definition-12.cfg",
    # base_path / "fig-1c" / "export_definition-16.cfg",
    # base_path / "fig-1c" / "export_definition-20.cfg",
    # base_path / "fig-1c" / "export_definition-24.cfg",
    # base_path / "fig-1c" / "export_definition-28.cfg",
    #
    # base_path / "fig-1d" / "export_definition-00.cfg",
    # base_path / "fig-1d" / "export_definition-06.cfg",
    # base_path / "fig-1d" / "export_definition-14.cfg",
    # base_path / "fig-1d" / "export_definition-17.cfg",
    # base_path / "fig-1d" / "export_definition-22.cfg",
    # base_path / "fig-1d" / "export_definition-26.cfg",
    # base_path / "fig-1d" / "export_definition-30.cfg",
    # ]
    # for cfg_path in cfg_path_list:
    #     log.info(f"Reading configuration file {cfg_path}")
    #     cfg = read_config(cfg_path)
    #     cfg.image_file.info.to_excel(cfg_path.parent / "movies_list.xls")
    #
    #     for ch in cfg.channels:
    #         # prepare path for exporting data
    #         export_path = ensure_dir(cfg_path.parent / "openvdb" / f"ch{ch:01d}")
    #         export_tiff_path = ensure_dir(cfg_path.parent / "tiff" / f"ch{ch:01d}")
    #
    #         frames = list(range(cfg.image_file.n_frames))
    #         vol_timeseries = bioformats_to_ndarray_zstack_timeseries(cfg.image_file, frames, roi=cfg.roi, channel=ch)
    #         plot_intensity_histogram(vol_timeseries, filename=cfg_path.parent / f"histogram_ch{ch}.pdf")
    #
    #         for fr, vol in enumerate(vol_timeseries):
    #             if fr not in cfg.frames:
    #                 continue
    #             vtkim = _ndarray_to_vtk_image(vol, um_per_pix=cfg.image_file.um_per_pix, um_per_z=cfg.um_per_z)
    #             _save_vtk_image_to_disk(vtkim, export_path / f"ch{ch:01d}_fr{fr:03d}.vdb")
    #             imwrite(export_tiff_path / f"ch{ch:01d}_fr{fr:03d}.tiff", vol, imagej=True, metadata={'order': 'ZXY'})
    #         with open(cfg_path.parent / "vol_info", "w") as f:
    #             f.write(f"min {np.min(vol_timeseries)} max {np.max(vol_timeseries)}")
    #
    # javabridge.kill_vm()

    red_trans_fn = "[0, 0.0, 0.0, 0.0, 12000, 1.0, 0.0, 0.0]"
    grn_trans_fn = "[0, 0.0, 0.0, 0.0, 12000, 0.0, 1.0, 0.0]"
    blu_trans_fn = "[0, 0.0, 0.0, 0.0, 12000, 0.0, 0.0, 1.0]"
    tfn_lst = [red_trans_fn, grn_trans_fn, blu_trans_fn]
    for cfg_path in cfg_path_list:
        log.info(f"Reading configuration file {cfg_path}")
        cfg = read_config(cfg_path)

        channels = dict()
        export_tiff_path = ensure_dir(cfg_path.parent / "tiff")
        vol_timeseries, ch_metadata = bioformats_to_tiffseries(cfg_struct=cfg, save_path=export_tiff_path,
                                                               until_frame=100)
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
                "minmax":              ch_metadata[chkey]["minmax"],
                "min":                 [mm[0] for mm in ch_metadata[chkey]["minmax"]],
                "max":                 [mm[1] for mm in ch_metadata[chkey]["minmax"]]
            }
        save_vtk_python_state(cfg_path.parent / f"paraview_state.py", channel_info=channels)

    javabridge.kill_vm()
