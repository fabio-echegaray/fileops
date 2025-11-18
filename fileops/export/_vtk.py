import numpy as np
import vtk

from fileops.logger import get_logger

log = get_logger(name='export-vtk')


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
