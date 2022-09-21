import os

from matplotlib.figure import Figure

import movierender.overlays as ovl
from fileops.cached import CachedImageFile
from fileops.logger import get_logger
from movierender import MovieRenderer, CompositeRGBImage
from movierender.overlays.pixel_tools import PixelTools

log = get_logger(name='movielayout')

alexa_488 = [.29, 1., 0]
alexa_594 = [1., .61, 0]
alexa_647 = [.83, .28, .28]
hoechst_33342 = [0, .57, 1.]
red = [1, 0, 0]
green = [0, 1, 0]
blue = [0, 0, 1]


def make_movie(im: CachedImageFile, suffix='', folder='.'):
    assert len(im.channels) >= 2, 'Image series contains less than two channels.'
    filename = os.path.basename(im.image_path) + suffix + ".twoch.mp4"
    base_folder = os.path.abspath(folder)
    path = os.path.join(base_folder, filename)
    if os.path.exists(path):
        log.warning(f'File {filename} already exists in folder {base_folder}.')
        return

    log.info(f'Making movie {filename} from file {os.path.basename(im.image_path)} in folder {base_folder}.')
    t = PixelTools(im)

    ar = float(im.height) / float(im.width)
    log.info(f'aspect ratio={ar}.')

    fig = Figure(frameon=False, figsize=(10, 10), dpi=150)
    ax = fig.gca()

    movren = MovieRenderer(fig=fig,
                           image=im,
                           fps=15,
                           bitrate="15M",
                           fontdict={'size': 12}) + \
             ovl.ScaleBar(um=10, lw=3, xy=t.xy_ratio_to_um(0.10, 0.05), fontdict={'size': 9}, ax=ax) + \
             ovl.Timestamp(xy=t.xy_ratio_to_um(0.02, 0.95), va='center', ax=ax) + \
             CompositeRGBImage(ax=ax,
                               zstack=4,
                               channeldict={
                                   'H2-RFP':  {
                                       'id':        0,
                                       'color':     red,
                                       'rescale':   True,
                                       'intensity': 0.5
                                   },
                                   'Sqh-GFP': {
                                       'id':        1,
                                       'color':     alexa_488,
                                       'rescale':   True,
                                       'intensity': 0.5
                                   },
                               })
    movren.render(filename=path)
