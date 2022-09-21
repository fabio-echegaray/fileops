import os

from matplotlib import pyplot as plt, gridspec

from fileops.cached import CachedImageFile

from movierender import MovieRenderer, SingleImage, CompositeRGBImage
from movierender.overlays.pixel_tools import PixelTools
import movierender.overlays as ovl

from fileops.logger import get_logger

log = get_logger(name='movielayout')

green = [0, 1, 0]


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

    fig = plt.figure(frameon=False, figsize=(10, 10), dpi=150)
    gs = gridspec.GridSpec(nrows=1, ncols=2)

    ax_ch1 = fig.add_subplot(gs[0, 0])
    ax_ch2 = fig.add_subplot(gs[0, 1])
    fig.subplots_adjust(left=0.125, right=0.9, bottom=0.1, top=0.99, wspace=0.01, hspace=0.01)
    movren = MovieRenderer(fig=fig,
                           image=im,
                           fps=15,
                           bitrate="15M",
                           fontdict={'size': 12}) + \
             ovl.ScaleBar(um=50, lw=3, xy=t.xy_ratio_to_um(0.80, 0.05), fontdict={'size': 9}, ax=ax_ch1) + \
             ovl.ScaleBar(um=50, lw=3, xy=t.xy_ratio_to_um(0.80, 0.05), fontdict={'size': 9}, ax=ax_ch2) + \
             ovl.Timestamp(xy=t.xy_ratio_to_um(0.02, 0.95), va='center', ax=ax_ch1) + \
             SingleImage(ax=ax_ch1, channel=0) + \
             CompositeRGBImage(ax=ax_ch2, channeldict={
                 'Channel2': {
                     'id':        1,
                     'color':     green,
                     'rescale':   True,
                     'intensity': 1.0
                 },
             })
    movren.render(filename=path)
