import io
import base64

import numpy as np
import javabridge

import PySimpleGUI as sg
from PIL import Image
from skimage.transform import resize

from fileops.cached import CachedImageFile
from fileops.export import bioformats_to_tiffseries
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

    img_struct = path = series = None
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
                img_struct = CachedImageFile(path, cache_results=False)
                series = [s.attrib['Name'] for s in img_struct.all_series]
            except:
                series = ["Error reading file."]
            window["-SERIES LIST-"].update(series)
        elif event == "-SERIES LIST-":  # A series was chosen from the listbox
            try:
                series = values["-SERIES LIST-"][0]
                img_struct.series = series
                ix = img_struct.ix_at(c=0, z=0, t=0)
                mdimg = img_struct.image(ix)
                window["-TOUT-"].update(series)

                img = (mdimg.image / mdimg.image.ptp()) * 255
                img = resize(image=img, output_shape=(400, 400))
                im_pil = Image.fromarray(img.astype(np.uint8))
                with io.BytesIO() as output:
                    im_pil.save(output, format="PNG")
                    data = output.getvalue()
                im_64 = base64.b64encode(data)
                window["-IMAGE-"].update(data=im_64)
            except:
                pass
        elif event == "-EXPORT-":
            bioformats_to_tiffseries(path, img_struct, save_folder=f'{series.replace(" ", "_")}_paraview')
    window.close()

    # open file and select timeseries

    # --------------------------------------
    #  Finish
    # --------------------------------------
    javabridge.kill_vm()
