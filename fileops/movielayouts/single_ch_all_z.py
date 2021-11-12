import os

import numpy as np

from matplotlib import pyplot as plt, gridspec

from fileops.cached import CachedImageFile
from fileops.movielayouts import scalebar

from movierender import MovieRenderer, SingleImage, CompositeRGBImage
from movierender.overlays.pixel_tools import PixelTools
import movierender.overlays as ovl

from fileops.logger import get_logger

log = get_logger(name='movielayout')

green = [0, 1, 0]


def make_movie(im: CachedImageFile, suffix='', folder='.'):
    assert len(im.channels) >= 2, 'Image series contains less than two channels.'
    print(im.info)
    print(im.zstacks)
    filename = os.path.basename(im.image_path) + suffix + ".all_z.mp4"
    base_folder = os.path.abspath(folder)
    path = os.path.join(base_folder, filename)
    if os.path.exists(path):
        log.warning(f'File {filename} already exists in folder {base_folder}.')
        return

    log.info(f'Making movie {filename} from file {os.path.basename(im.image_path)} in folder {base_folder}.')
    t = PixelTools(im)

    n_cols = 4
    n_rows = int(np.ceil(len(im.zstacks) / n_cols))
    mag = im.magnification
    ar = float(im.height) / float(im.width)
    log.info(f'aspect ratio={ar}.')
    log.info(f'number of stacks={len(im.zstacks)}, n_rows={n_rows}.')

    fig = plt.figure(frameon=False, figsize=(10, 10), dpi=150)
    gs = gridspec.GridSpec(nrows=n_rows, ncols=n_cols)

    # set positions of scale bars and text
    scale_xy = t.xy_ratio_to_um(0.80, 0.05)
    ztext_xy = t.xy_ratio_to_um(0.70, 0.95)

    # first axes is for BF
    ax_ch1 = fig.add_subplot(gs[0, 0])
    fig.subplots_adjust(left=0.125, right=0.9, bottom=0.1, top=0.99, wspace=0.01, hspace=0.01)
    movren = MovieRenderer(fig=fig,
                           image=im,
                           fps=15,
                           bitrate="15M",
                           fontdict={'size': 12}) + \
             ovl.ScaleBar(um=scalebar[mag], lw=3, xy=scale_xy, fontdict={'size': 7}, ax=ax_ch1) + \
             ovl.Timestamp(xy=t.xy_ratio_to_um(0.02, 0.95), va='center', ax=ax_ch1) + \
             SingleImage(ax=ax_ch1, channel=0)

    # rest of grid is for the channel of interest across all Z
    for grid_pos in zip(np.repeat(np.arange(n_rows), n_cols), np.tile(np.arange(n_cols), n_rows)):
        row, col = grid_pos
        z_ix = row * n_cols + col - 1
        if grid_pos != (0, 0) and z_ix < len(im.zstacks):
            ax_z = fig.add_subplot(gs[grid_pos[0], grid_pos[1]])
            zpos = im.zstacks[z_ix]
            movren = movren + \
                     CompositeRGBImage(ax=ax_z, zstack=zpos, channeldict={
                         'Channel2': {
                             'id':        1,
                             'color':     green,
                             'rescale':   True,
                             'intensity': 1.0
                         },
                     }) + \
                     ovl.ScaleBar(um=scalebar[mag], lw=3, xy=scale_xy, fontdict={'size': 7}, ax=ax_z) + \
                     ovl.Text(f'z={zpos * im.um_per_z} [um]', xy=ztext_xy, fontdict={'size': 7}, ax=ax_z)
    movren.render(filename=path, test=False)
