import os.path

import numpy as np
import vtk
from vtkmodules.vtkIOOpenVDB import vtkOpenVDBWriter

from fileops.export import bioformats_to_ndarray_zstack_timeseries
from fileops.export.config import ConfigVolume
from fileops.logger import get_logger
from fileops.pathutils import ensure_dir

log = get_logger(name='export-vtk')


def export_openvdb(cfg_vol: ConfigVolume, **kwargs):
    log.info(f"Exporting data from configuration file {cfg_vol.configfile} into a OpenVDB format.")

    for ch in cfg_vol.channels:
        # prepare path for exporting data
        export_path = ensure_dir(cfg_vol.path / "openvdb" / f"ch{ch:01d}")
        # export_tiff_path = ensure_dir(cfg_vol.path / "tiff" / f"ch{ch:01d}")

        frames = list(range(cfg_vol.image_file.n_frames))
        vol_timeseries = bioformats_to_ndarray_zstack_timeseries(cfg_vol.image_file, frames, channel=ch)

        for fr, vol in enumerate(vol_timeseries):
            if fr not in cfg_vol.frames:
                continue
            vtkim = _ndarray_to_vtk_image(vol, um_per_pix=cfg_vol.image_file.um_per_pix, um_per_z=cfg_vol.um_per_z)
            _save_vtk_image_to_disk_as_openvdb(vtkim, export_path / f"ch{ch:01d}_fr{fr:03d}.vdb")
            # imwrite(export_tiff_path / f"ch{ch:01d}_fr{fr:03d}.tiff", vol, imagej=True, metadata={'order': 'ZXY'})
        with open(cfg_vol.path / "vol_info", "w") as f:
            f.write(f"min {np.min(vol_timeseries)} max {np.max(vol_timeseries)}")


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
