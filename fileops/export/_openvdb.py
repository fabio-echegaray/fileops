import os.path

import numpy as np
import vtk
from scipy import stats

from fileops.export import bioformats_to_ndarray_zstack_timeseries
from fileops.export.config import ConfigVolume
from fileops.logger import get_logger
from fileops.pathutils import ensure_dir

log = get_logger(name='export-vtk')
try:
    from vtkmodules.vtkIOOpenVDB import vtkOpenVDBWriter

    __OPENVDB_OK__ = True
except ImportError:
    log.warning("Could not import VTK related modules to export in OpenVDB format.")
    __OPENVDB_OK__ = True


def export_openvdb(cfg_vol: ConfigVolume, **kwargs):
    if not __OPENVDB_OK__:
        log.error("No VTK module to export in OpenVDB format.")
        return

    log.info(f"Exporting data from configuration file {cfg_vol.configfile} into a OpenVDB format.")

    for ch in cfg_vol.channels:
        # prepare path for exporting data
        export_path = ensure_dir(cfg_vol.path / "openvdb" / f"ch{ch:01d}")

        frames = cfg_vol.frames
        log.debug(f"frames: {frames}")

        vol_timeseries = bioformats_to_ndarray_zstack_timeseries(cfg_vol.image_file, frames, channel=ch)
        # convert to 8-bit data and normalize intensities across whole timeseries
        vol_timeseries = ((vol_timeseries - vol_timeseries.min()) / vol_timeseries.ptp() * 255.0).astype(np.uint8)

        for fr, vol in enumerate(vol_timeseries):
            if fr not in cfg_vol.frames:
                continue
            vtkim = _ndarray_to_vtk_image(vol, um_per_pix=cfg_vol.image_file.um_per_pix, um_per_z=cfg_vol.um_per_z)
            _save_vtk_image_to_disk_as_openvdb(vtkim, export_path / f"vol_ch{ch:01d}_fr{fr:03d}.vdb")
            with open(cfg_vol.path / "vol_info", "a") as f:
                f.write(f"fr {fr:04d}: ch {ch:02d} min {np.min(vol):.4f} max {np.max(vol):.4f} "
                        f"avg {np.mean(vol):.4f} std {np.std(vol):.4f} mode {stats.mode(vol, axis=None).mode:.4f}\n")
        with open(cfg_vol.path / "vol_info", "a") as f:
            f.write(f"vol: ch {ch:02d} min {np.min(vol_timeseries):.4f} max {np.max(vol_timeseries):.4f} "
                    f"avg {np.mean(vol_timeseries):.4f} std {np.std(vol_timeseries):.4f} mode {stats.mode(vol, axis=None).mode:.4f}\n")


def _ndarray_to_vtk_image(data: np.ndarray, um_per_pix=1.0, um_per_z=1.0):
    ztot, col, row = data.shape

    # For VTK to be able to use the data, it must be stored as a VTK-image.
    vtk_image = vtk.vtkImageImport()
    data_string = data.tobytes()
    vtk_image.CopyImportVoidPointer(data_string, len(data_string))
    # The type of the newly imported data is set to unsigned char (uint8)
    vtk_image.SetDataScalarTypeToUnsignedChar()

    # dimensions of the array that data is stored in.
    vtk_image.SetNumberOfScalarComponents(1)
    vtk_image.SetScalarArrayName("density")
    vtk_image.SetDataExtent(1, row, 1, col, 1, ztot)
    vtk_image.SetWholeExtent(1, row, 1, col, 1, ztot)

    # scale data to calibration in micrometers
    vtk_image.SetDataSpacing(um_per_pix, um_per_pix, um_per_z)

    return vtk_image


def _save_vtk_image_to_disk_as_openvdb(vtk_image, filename):
    writer = vtkOpenVDBWriter()
    writer.SetInputConnection(vtk_image.GetOutputPort())
    if os.path.exists(filename):
        os.remove(filename)
    writer.SetFileName(filename)
    writer.Update()
