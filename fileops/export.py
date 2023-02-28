import configparser
import os.path
from collections import namedtuple
from pathlib import Path
from typing import List

import javabridge
import numpy as np
import vtk
from tifffile import imwrite
from vtkmodules.vtkIOOpenVDB import vtkOpenVDBWriter
from roifile import ImagejRoi

from fileops.cached import CachedImageFile
from fileops.cached.cached_image_file import ensure_dir
from fileops.image import OMEImageFile
from fileops.logger import get_logger

log = get_logger(name='export')


def bioformats_to_tiffseries(path, img_struct: CachedImageFile, save_folder='_vol_paraview'):
    log.info("Exporting bioformats file to series of tiff file volumes.")
    base_dir = os.path.dirname(path)
    sav_path = os.path.join(base_dir, save_folder)
    ensure_dir(os.path.join(sav_path, 'dummy'))

    image = np.empty(shape=(len(img_struct.zstacks), *img_struct.image(0).image.shape), dtype=np.uint16)
    for j, c in enumerate(img_struct.channels):
        for fr in img_struct.frames:
            for i, z in enumerate(img_struct.zstacks):
                ix = img_struct.ix_at(c=j, z=z, t=fr)
                mdimg = img_struct.image(ix)
                image[i, :, :] = mdimg.image
            fname = f'C{c:02d}T{fr:04d}_vol.tiff'
            fpath = os.path.join(sav_path, fname)
            log.debug(f"Saving image {fname} in cache (path={fpath}).")
            imwrite(fpath, np.array(image), imagej=True, metadata={'order': 'ZXY'})


def bioformats_to_ndarray_zstack(img_struct: OMEImageFile, roi=None, channel=0, frame=0):
    log.info("Exporting bioformats file to a single ndarray representing a z-stack volume.")

    if roi is not None:
        log.debug("Processing ROI definition that is in configuration file")
        w = abs(roi.right - roi.left)
        h = abs(roi.top - roi.bottom)
        x0 = int(roi.left)
        y0 = int(roi.top)
        x1 = int(x0 + w)
        y1 = int(y0 + h)
    else:
        log.debug("No ROI definition in configuration file")
        w = img_struct.width
        h = img_struct.height
        x0 = 0
        y0 = 0
        x1 = w
        y1 = h

    image = np.empty(shape=(len(img_struct.zstacks), h, w), dtype=np.uint16)
    for i, z in enumerate(img_struct.zstacks):
        log.debug(f"c={channel}, z={z}, t={frame}")
        ix = img_struct.ix_at(c=channel, z=z, t=frame)
        mdimg = img_struct.image(ix)
        image[i, :, :] = mdimg.image[y0:y1, x0:x1]

    # convert to 8 bit data
    image = ((image - image.min()) / (image.ptp() / 255.0)).astype(np.uint8)

    return image


def bioformats_to_ndarray_zstack_timeseries(img_struct: OMEImageFile, frames: List[int], roi=None, channel=0):
    """
    Constructs a memory-intensive numpy ndarray of a whole OMEImageFile timeseries.
    Warning, it can lead to memory issues on machines with low RAM.
    """
    log.info("Exporting bioformats file to and ndarray representing a series of z-stack volumes.")

    if roi is not None:
        log.debug("Processing ROI definition that is in configuration file")
        w = abs(roi.right - roi.left)
        h = abs(roi.top - roi.bottom)
        x0 = int(roi.left)
        y0 = int(roi.top)
        x1 = int(x0 + w)
        y1 = int(y0 + h)
    else:
        log.debug("No ROI definition in configuration file")
        w = img_struct.width
        h = img_struct.height
        x0 = 0
        y0 = 0
        x1 = w
        y1 = h

    image = np.empty(shape=(len(frames), len(img_struct.zstacks), h, w), dtype=np.uint16)
    for i, frame in enumerate(frames):
        for j, z in enumerate(img_struct.zstacks):
            log.debug(f"c={channel}, z={z}, t={frame}")
            ix = img_struct.ix_at(c=channel, z=z, t=frame)
            mdimg = img_struct.image(ix)
            image[i, j, :, :] = mdimg.image[y0:y1, x0:x1]

    # convert to 8 bit data and normalize intensities across whole timeseries
    image = ((image - image.min()) / (image.ptp() / 255.0)).astype(np.uint8)

    return image


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


def _show_vtk_volume(volume):
    # With almost everything else ready, its time to initialize the renderer and window, as well as
    #  creating a method for exiting the application
    renderer = vtk.vtkRenderer()
    renderWin = vtk.vtkRenderWindow()
    renderWin.AddRenderer(renderer)
    renderInteractor = vtk.vtkRenderWindowInteractor()
    renderInteractor.SetRenderWindow(renderWin)

    # We add the volume to the renderer ...
    renderer.AddVolume(volume)
    colors = vtk.vtkNamedColors()
    renderer.SetBackground(colors.GetColor3d("MistyRose"))

    # ... and set window size.
    renderWin.SetSize(1000, 1000)

    # A simple function to be called when the user decides to quit the application.
    def exitCheck(obj, event):
        if obj.GetEventPending() != 0:
            obj.SetAbortRender(1)

    # Tell the application to use the function as an exit check.
    renderWin.AddObserver("AbortCheckEvent", exitCheck)

    renderInteractor.Initialize()
    # Because nothing will be rendered without any input, we order the first render manually
    #  before control is handed over to the main-loop.
    renderWin.Render()
    renderInteractor.Start()


def save_ndarray_as_vdb(data: np.ndarray, um_per_pix=1.0, um_per_z=1.0, filename="output.vdb"):
    vtkim = _ndarray_to_vtk_image(data, um_per_pix=um_per_pix, um_per_z=um_per_z)
    _save_vtk_image_to_disk(vtkim, filename)


# ------------------------------------------------------------------------------------------------------------------
#  routines for handling of configuration files
# ------------------------------------------------------------------------------------------------------------------
ExportConfig = namedtuple('ExportConfig', ['series', 'frames', 'channels', 'path', 'name', 'image_file', 'roi', ])


def _load_project_file(path) -> configparser.ConfigParser:
    prj = configparser.ConfigParser()
    prj.read(path)

    return prj


def read_config(cfg_path) -> ExportConfig:
    cfg = _load_project_file(cfg_path)

    im_series = int(cfg["DATA"]["series"])
    im_frame = cfg["DATA"]["frame"]
    im_channel = cfg["DATA"]["channel"]
    img_path = Path(cfg["DATA"]["image"])

    # process ROI path
    roi_path = Path(cfg["DATA"]["ROI"])
    if not roi_path.is_absolute():
        roi_path = cfg_path.parent / roi_path

    img_file = OMEImageFile(img_path.as_posix(), image_series=im_series)
    return ExportConfig(series=im_series,
                        frames=range(img_file.n_frames) if im_frame == "all" else int(im_frame),
                        channels=range(img_file.n_channels) if im_channel == "all" else int(im_channel),
                        path=cfg_path.parent,
                        name=cfg_path.name,
                        image_file=img_file,
                        roi=ImagejRoi.fromfile(roi_path))


def _test_shape():
    vol = np.ones(shape=(100, 100, 100), dtype=np.uint8)
    vol[10:20, 10:20, 10:20] = 30
    vol[20:40, 20:40, 20:40] = 70
    vol[40:50, 40:50, 40:50] = 150
    vol[80:90, 80:90, 80:90] = 240

    return vol


if __name__ == "__main__":
    base_path = Path("/home/lab/Documents/Fabio/Blender")
    cfg_path_list = [
        base_path / "fig-1a" / "export_definition.cfg",
        base_path / "fig-1b" / "export_definition.cfg",
        base_path / "fig-1c" / "export_definition.cfg",
        base_path / "fig-1d" / "export_definition.cfg",
        base_path / "fig-1e" / "export_definition.cfg",
        base_path / "fig-1f" / "export_definition.cfg",
    ]
    for cfg_path in cfg_path_list:
        cfg = read_config(cfg_path)

        for ch in cfg.channels:
            # prepare path for exporting data
            export_path = ensure_dir(cfg_path.parent / "openvdb" / f"ch{ch:01d}")

            vol_timeseries = bioformats_to_ndarray_zstack_timeseries(cfg.image_file, cfg.frames, roi=cfg.roi,
                                                                     channel=ch)
            for fr, vol in enumerate(vol_timeseries):
                vtkim = _ndarray_to_vtk_image(vol, um_per_pix=cfg.image_file.um_per_pix,
                                              um_per_z=cfg.image_file.um_per_z)
                _save_vtk_image_to_disk(vtkim, export_path / f"vol_ch{ch:01d}_fr{fr:03d}.vdb")

    javabridge.kill_vm()

    vtkvol = _vtk_image_to_vtk_volume(vtkim)
    _show_vtk_volume(vtkvol)
