import io
import base64
from pathlib import Path

import numpy as np

import PySimpleGUI as sg
from skimage.transform import resize

import imageio.v3 as iio
from fileops.export import bioformats_to_tiffseries
from fileops.export.config import ExportConfig
from fileops.image import OMEImageFile
from fileops.logger import get_logger

log = get_logger(name='__main__')

if __name__ == "__main__":

    file_list_column = [
        [
            sg.Text("Image File"),
            sg.In(size=(25, 1), enable_events=True, key="-FILE-"),
            sg.FileBrowse(file_types=[('Volocity files', '*.mvd2'), ('Nikon files', '*.nd2')]),
        ],
        [
            sg.Listbox(
                values=[], enable_events=True, size=(40, 20), key="-SERIES LIST-"
            )
        ],
    ]
    image_viewer_column = [
        [sg.Text("Choose an image series from list on left:")],
        [sg.Text(size=(40, 1), key="-TOUT-")],
        [sg.Image(key="-IMAGE-", size=(400, 400), background_color="white")],
        [sg.Button(size=(10, 1), button_text='Export', enable_events=True, key="-EXPORT-"),
         ],
    ]
    layout = [
        [
            sg.Column(file_list_column),
            sg.VSeperator(),
            sg.Column(image_viewer_column),
        ]
    ]
    # Create the window
    window = sg.Window("Bioformats (Volocity, Nikon) to Tiff", layout)

    img_file = path = series = None
    # Create an event loop
    while True:
        event, values = window.read()
        # End program if user closes window or
        # presses the OK button
        if event == "OK" or event == sg.WIN_CLOSED:
            break
        elif event == "-FILE-":
            path = values["-FILE-"]
            try:
                img_file = OMEImageFile(path)
                series = [s.attrib['Name'] for s in img_file.all_series]
            except:
                series = ["Error reading file."]
            window["-SERIES LIST-"].update(series)
        elif event == "-SERIES LIST-":  # A series was chosen from the listbox
            try:
                series = values["-SERIES LIST-"][0]
                img_file.series = series
                ix = img_file.ix_at(c=0, z=0, t=0)
                mdimg = img_file.image(ix)
                window["-TOUT-"].update(series)

                img = (mdimg.image / mdimg.image.ptp()) * 255
                img = resize(image=img, output_shape=(400, 400))
                with io.BytesIO() as output:
                    iio.imwrite(output, img.astype(np.uint8))
                    data = output.getvalue()
                im_64 = base64.b64encode(data)
                window["-IMAGE-"].update(data=im_64)
            except:
                pass
        elif event == "-EXPORT-":
            exp = ExportConfig(series=img_file.series,
                               frames=img_file.frames,
                               channels=img_file.channels,
                               failover_dt=None,
                               failover_mag=None,
                               path=img_file.base_path,
                               name=img_file.image_path.name,
                               image_file=img_file,
                               um_per_z=img_file.um_per_z,
                               roi=None,
                               title="",
                               fps=1,
                               movie_filename="",
                               layout="")
            bioformats_to_tiffseries(exp, save_path=Path(f'{series.replace(" ", "_")}_paraview'))
    window.close()
