import os.path
from pathlib import Path

import numpy as np
import vtk
from tifffile import imwrite
from vtkmodules.vtkIOOpenVDB import vtkOpenVDBWriter

from fileops.export import bioformats_to_ndarray_zstack_timeseries
from fileops.export.config import ExportConfig
from fileops.logger import get_logger
from fileops.pathutils import ensure_dir

log = get_logger(name='export-vtk')


def save_ndarray_as_vdb(data: np.ndarray, um_per_pix=1.0, um_per_z=1.0, filename="output.vdb"):
    vtkim = _ndarray_to_vtk_image(data, um_per_pix=um_per_pix, um_per_z=um_per_z)
    _save_vtk_image_to_disk(vtkim, filename)


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


def _vtk_image_to_vtk_volume(vtk_image):
    # The following class is used to store transparency-values for later retrival.
    #  In our case, we want the value 0 to be
    # completely transparent and 1 completely opaque.
    alphaChannelFunc = vtk.vtkPiecewiseFunction()
    # alphaChannelFunc.AddPoint(0, 1.0)
    # alphaChannelFunc.AddPoint(np.iinfo(np.uint8).max, 0.01)
    alphaChannelFunc.AddPoint(0, 0.01)
    alphaChannelFunc.AddPoint(np.iinfo(np.uint8).max, 1.0)

    # This class stores color data and can create color tables from a few color points.
    #  For this demo, we want the three cubes to be of the colors red green and blue.
    num = 20
    scale = np.logspace(-1, 1, num=num)
    colorFunc = vtk.vtkColorTransferFunction()
    for intensity, color in zip(np.linspace(0, np.iinfo(np.uint8).max, num=num), scale):
        # print(f"{intensity:.2f}, {color:.2f}")
        colorFunc.AddRGBPoint(intensity, color, color, color)

    # The previous two classes stored properties.
    #  Because we want to apply these properties to the volume we want to render,
    # we have to store them in a class that stores volume properties.
    volumeProperty = vtk.vtkVolumeProperty()
    volumeProperty.SetColor(colorFunc)
    volumeProperty.SetScalarOpacity(alphaChannelFunc)

    volumeMapper = vtk.vtkFixedPointVolumeRayCastMapper()
    volumeMapper.SetInputConnection(vtk_image.GetOutputPort())

    # The class vtkVolume is used to pair the previously declared volume as well as the properties
    #  to be used when rendering that volume.
    volume = vtk.vtkVolume()
    volume.SetMapper(volumeMapper)
    volume.SetProperty(volumeProperty)

    return volume


def _save_vtk_image_to_disk(vtk_image, filename):
    writer = vtkOpenVDBWriter()
    writer.SetInputConnection(vtk_image.GetOutputPort())
    if os.path.exists(filename):
        os.remove(filename)
    writer.SetFileName(filename)
    writer.Update()


def export_vtk(cfg: ExportConfig, out_path: Path, until_frame=np.inf):
    log.info(f"Exporting data from configuration file {cfg.path} into VTK format")
    # cfg.image_file.info.to_excel(cfg.path.parent / "movies_list.xls")

    for ch in cfg.channels:
        # prepare path for exporting data
        export_path = ensure_dir(cfg.path.parent / "openvdb" / f"ch{ch:01d}")
        export_tiff_path = ensure_dir(cfg.path.parent / "tiff" / f"ch{ch:01d}")

        frames = list(range(cfg.image_file.n_frames))
        vol_timeseries = bioformats_to_ndarray_zstack_timeseries(cfg.image_file, frames, roi=cfg.roi, channel=ch)
        # plot_intensity_histogram(vol_timeseries, filename=cfg_path.parent / f"histogram_ch{ch}.pdf")

        for fr, vol in enumerate(vol_timeseries):
            if fr not in cfg.frames:
                continue
            vtkim = _ndarray_to_vtk_image(vol, um_per_pix=cfg.image_file.um_per_pix, um_per_z=cfg.um_per_z)
            _save_vtk_image_to_disk(vtkim, export_path / f"ch{ch:01d}_fr{fr:03d}.vdb")
            imwrite(export_tiff_path / f"ch{ch:01d}_fr{fr:03d}.tiff", vol, imagej=True, metadata={'order': 'ZXY'})
        with open(cfg.path.parent / "vol_info", "w") as f:
            f.write(f"min {np.min(vol_timeseries)} max {np.max(vol_timeseries)}")
