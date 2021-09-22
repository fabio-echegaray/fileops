import os

from matplotlib import pyplot as plt

from cached import CachedImageFile

from movierender import MovieRenderer, SingleImage
from movierender.overlays.pixel_tools import PixelTools
import movierender.overlays as ovl

from logger import get_logger

log = get_logger(name='movielayout')


def make_movie(im: CachedImageFile, suffix='', folder='.'):
    filename = os.path.basename(im.image_path) + suffix + ".mp4"
    base_folder = os.path.abspath(folder)
    path = os.path.join(base_folder, filename)
    if os.path.exists(path):
        log.warning(f'File {filename} already exists in folder {base_folder}.')
        return

    log.info(f'Making movie {filename} from file {os.path.basename(im.image_path)} in folder {base_folder}.')
    t = PixelTools(im)

    fig = plt.figure(frameon=False, figsize=(5, 5), dpi=150)
    movren = MovieRenderer(image=im,
                           fig=fig,
                           fps=15,
                           show_axis=False,
                           bitrate="10M",
                           fontdict={'size': 12}) + \
             ovl.ScaleBar(um=50, lw=3, xy=t.xy_ratio_to_um(0.80, 0.05), fontdict={'size': 9}) + \
             ovl.Timestamp(xy=t.xy_ratio_to_um(0.02, 0.95), va='center') + \
             SingleImage()
    movren.render(filename=path, test=False)
