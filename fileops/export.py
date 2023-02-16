import os.path
from pathlib import Path

import javabridge
import numpy as np
import vtk
from tifffile import imwrite
from vtkmodules.vtkIOOpenVDB import vtkOpenVDBWriter

from cached import CachedImageFile
from cached.cached_image_file import ensure_dir
from fileops.image import OMEImageFile
from logger import get_logger

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


def bioformats_to_ndarray_zstack(img_struct: OMEImageFile, channel=0, frame=0):
    log.info("Exporting bioformats file to series of tiff file volumes.")

    image = np.empty(shape=(len(img_struct.zstacks), *img_struct.image(0).image.shape), dtype=np.uint16)
    for i, z in enumerate(img_struct.zstacks):
        log.debug(f"c={channel}, z={z}, t={frame}")
        ix = img_struct.ix_at(c=channel, z=z, t=frame)
        mdimg = img_struct.image(ix)
        image[i, :, :] = mdimg.image

    # convert to 8 bit data
    image = ((image - image.min()) / (image.ptp() / 255.0)).astype(np.uint8)

    return image


def _ndarray_to_vtk_image(data: np.ndarray, um_per_pix=1.0, um_per_z=1.0):
    ztot, col, row = data.shape
    ztot, col, row = ztot - 1, col - 1, row - 1

    # For VTK to be able to use the data, it must be stored as a VTK-image.
    vtk_image = vtk.vtkImageImport()
    data_string = data.tobytes()
    vtk_image.CopyImportVoidPointer(data_string, len(data_string))
    # The type of the newly imported data is set to unsigned char (uint8)
    vtk_image.SetDataScalarTypeToUnsignedChar()

    # dimensions of the array that data is stored in.
    vtk_image.SetNumberOfScalarComponents(1)
    vtk_image.SetScalarArrayName("density")
    vtk_image.SetDataExtent(0, row, 0, col, 0, ztot)
    vtk_image.SetWholeExtent(0, row, 0, col, 0, ztot)

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


if __name__ == "__main__":
    im_series = 2
    data_path = Path("/media/lab/Data/Mustafa/")
    cache_root_path = Path("/media/lab/cache/segmentation_agents/")
    exp_name = "Sqh-GFP_H2-RFP_WT_Zeiss_20210330"
    exp_file = f"{exp_name}.mvd2"
    img_path = data_path / exp_name / exp_file

    ch = 0
    img_file = OMEImageFile(img_path.as_posix(), image_series=im_series)
    for fr in range(img_file.n_frames):
        vol = bioformats_to_ndarray_zstack(img_file, frame=fr, channel=ch)
        vtkim = _ndarray_to_vtk_image(vol, um_per_pix=img_file.um_per_pix, um_per_z=img_file.um_per_z)
        _save_vtk_image_to_disk(vtkim, f"vol_ch{ch:01d}_fr{fr:03d}.vdb")

    javabridge.kill_vm()

    vtkvol = _vtk_image_to_vtk_volume(vtkim)
    _show_vtk_volume(vtkvol)
