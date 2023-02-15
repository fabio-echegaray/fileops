import os.path
import pickle
from pathlib import Path

import javabridge
import numpy as np
import vtk
from tifffile import imsave
import tifffile as tf
from pyevtk.hl import gridToVTK
from vtkmodules.vtkIOOpenVDB import vtkOpenVDBWriter
# import pyopenvdb as vdb

from cached import CachedImageFile
from cached.cached_image_file import ensure_dir
from fileops.image import OMEImageFile, to_8bit
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
            imsave(fpath, np.array(image), imagej=True, metadata={'order': 'ZXY'})


def bioformats_to_vtk(img_struct: OMEImageFile):
    log.info("Exporting bioformats file to series of tiff file volumes.")
    # base_dir = os.path.dirname(path)
    # sav_path = os.path.join(base_dir, save_folder)
    # ensure_dir(os.path.join(sav_path, 'dummy'))

    image = np.empty(shape=(len(img_struct.zstacks), *img_struct.image(0).image.shape), dtype=np.uint16)
    # for j, c in enumerate(img_struct.channels):
    # for fr in img_struct.frames:
    j = 1
    fr = 45
    for i, z in enumerate(img_struct.zstacks):
        print(f"c={j}, z={z}, t={fr}")
        ix = img_struct.ix_at(c=j, z=z, t=fr)
        mdimg = img_struct.image(ix)
        image[i, :, :] = mdimg.image

    return image


# def _save_narray_to_vtk(data: np.ndarray):
#     # z, w, h = data.shape
#     w, h, z = data.shape
#
#     x = np.arange(0, w + 1)
#     y = np.arange(0, h + 1)
#     z = np.arange(0, z + 1)
#
    # gridToVTK("./data", x, y, z, cellData={'data': data})


def _save_narray_to_vtk(data: np.ndarray):
    print(data.shape)
    data = ((data - data.min()) / (data.ptp() / 255.0)).astype(np.uint8)

    # z, w, h = data.shape
    # row, col, ztot = h, w, z
    ztot, col, row = data.shape
    ztot, col, row = ztot-1, col-1, row-1

    # For VTK to be able to use the data, it must be stored as a VTK-image.
    dataImporter = vtk.vtkImageImport()
    # The previously created array is converted to a string of chars and imported.
    data_string = data.tobytes()
    dataImporter.CopyImportVoidPointer(data_string, len(data_string))
    # The type of the newly imported data is set to unsigned char (uint8)
    dataImporter.SetDataScalarTypeToUnsignedChar()
    # dataImporter.SetDataScalarTypeToUnsignedShort()

    # Because the data that is imported only contains an intensity value
    #  (it isn't RGB-coded or something similar), the importer must be told this is the case.
    dataImporter.SetNumberOfScalarComponents(1)
    # The following two functions describe how the data is stored and the dimensions of the array it is stored in.
    #  For this simple case, all axes are of length 75 and begins with the first element.
    #  For other data, this is probably not the case.
    # I have to admit however, that I honestly d ont know the difference between SetDataExtent()
    #  and SetWholeExtent() although VTK complains if not both are used.
    dataImporter.SetDataExtent(0, row, 0, col, 0, ztot)
    dataImporter.SetWholeExtent(0, row, 0, col, 0, ztot)

    # The following class is used to store transparency-values for later retrival.
    #  In our case, we want the value 0 to be
    # completely opaque whereas the three different cubes are given different transparency-values to show how it works.
    alphaChannelFunc = vtk.vtkPiecewiseFunction()
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
    volumeMapper.SetInputConnection(dataImporter.GetOutputPort())

    # The class vtkVolume is used to pair the previously declared volume as well as the properties
    #  to be used when rendering that volume.
    volume = vtk.vtkVolume()
    volume.SetMapper(volumeMapper)
    volume.SetProperty(volumeProperty)

    writer = vtk.vtkOpenVDBWriter()
    writer.SetInputConnection(dataImporter.GetOutputPort())
    fileName = "output.vdb"
    if os.path.exists(fileName):
        os.remove(fileName)
    writer.SetFileName(fileName)
    writer.Update()

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

    # with tf.TiffFile(img_path) as tif:
    #     # data_matrix = tif.asarray()[10, :]
    #     print(tif.asarray().shape)


    # img_file = OMEImageFile(img_path.as_posix(), image_series=im_series)
    # vol = bioformats_to_vtk(img_file)
    # with open("volume.pkl", "wb") as f:
    #     pickle.dump(vol, f)
    # javabridge.kill_vm()

    with open("volume.pkl", "rb") as f:
        vol = pickle.load(f)

    _save_narray_to_vtk(vol)
