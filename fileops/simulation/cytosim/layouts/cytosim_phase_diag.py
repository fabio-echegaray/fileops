import multiprocessing
import os
from pathlib import Path
import shutil

import asyncpool
import logging
import asyncio

import imageio
import matplotlib

matplotlib.use('Agg')
import matplotlib.gridspec as gridspec
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from moviepy.video.VideoClip import VideoClip
from moviepy.video.io.bindings import mplfig_to_npimage

import movierender.overlays as ovl
from fileops.movielayouts import scalebar
from fileops.pathutils import ensure_dir
from movierender import MovieRenderer, SingleImage, DataTimeseries, PixelTools

from fileops.logger import get_logger

log = get_logger(name='cytosim-movielayout')


def make_movie(sim: pd.DataFrame, suffix='', folder='.'):
    fname = "test" + suffix + ".cytosim.mp4"
    path = os.path.join(ensure_dir(folder), fname)
    if os.path.exists(path):
        log.warning(f'File {fname} already exists in folder {folder}.')
        return

    log.info(f'Making movie {fname} in folder {folder}')

    colors = sns.color_palette('muted', len(tracks))
    style_d = {s: {'color': c} for s, c in zip(tracks, colors)}

    fig = plt.figure(frameon=False, figsize=(10, 10), dpi=150)
    gs = gridspec.GridSpec(nrows=2, ncols=2, height_ratios=[2, 1])

    ax_img = fig.add_subplot(gs[0, 0])
    ax_flw = fig.add_subplot(gs[0, 1])
    ax_tms = fig.add_subplot(gs[1:, :])
    fig.subplots_adjust(left=0.125, right=0.9, bottom=0.1, top=0.99, wspace=0.01, hspace=0.01)
    movren = MovieRenderer(fig=fig,
                           image=bf,
                           fps=10,
                           bitrate="5M",
                           fontdict={'size': 12}) + \
             ovl.ScaleBar(ax=ax_img, um=scalebar[mag], lw=3, xy=t.xy_ratio_to_um(0.80, 0.05), fontdict={'size': 9}) + \
             ovl.Timestamp(ax=ax_img, xy=t.xy_ratio_to_um(0.02, 0.95), va='center') + \
             SingleImage(ax=ax_img) + \
             FlowOverlay(bf, ax=ax_flw) + \
             AvgSignalsOverlay(bf, ax=ax_flw, style_dict=style_d, arrow_ang=angle_fmax, arrow_len=scalebar[mag],
                               xy=t.xy_ratio_to_um(0.90, 0.05)) + \
             DataTimeseries(flow, x='time', y='value',
                            ax=ax_tms, show_axis=True,
                            style_dict=style_d,
                            hue='signal', units='unit', estimator=None)
    movren.render(filename=path)


def render_last_frame(df: pd.DataFrame):
    # build dataframe of last image given condition coordinates
    for c0 in condition0:
        T = []
        for c1 in condition1:
            for c2 in condition2:
                r = df.query('N_fil==@c0 and N_crs==@c1 and N_myo==@c2')
                im_path = f"{cytosim_fld}actomyosin_sweep/treadmill/{r['run'].values[0]}/image1000.png"
                T.append({'crs':     c1,
                          'myo':     c2,
                          'picture': imageio.imread(im_path),
                          })
        ph = pd.DataFrame(T)

        grid = sns.FacetGrid(ph, row='crs', col='myo', height=1, aspect=1, margin_titles=True, despine=True)
        grid.map(lambda x, **kwargs: (plt.imshow(x.values[0]), plt.grid(False)), 'picture')
        grid.set_xlabels("")
        grid.set(xticks=[], yticks=[])
        grid.set_titles(row_template="{row_var} {row_name}k", col_template="{col_var} {col_name}k")
        grid.fig.suptitle(f"{int(c0 * 1000)} filaments")
        grid.tight_layout()
        grid.fig.subplots_adjust(wspace=0, hspace=0)
        grid.savefig(f"f{int(c0 * 1000):05d}-c{int(c1 * 1000):05d}-m{int(c2 * 1000):05d}.pdf")


if __name__ == "__main__":
    global _last_f, _render

    _last_f = -1
    _render = np.zeros((1, 1))

    # build dataframe of images
    print("Reading dataframe...")
    cytosim_lst = Path(
        '/media/lab/Data/Fabio/Dev/Python-actomyosin-furrows/cytosim/actomyosin_sweep/treadmill/simulations.csv')
    df = (pd.read_csv(cytosim_lst, skipinitialspace=True)
          .drop(columns='n')
          .query("N_fil==9000")
          )
    df['run'] = df['file'].apply(lambda r: 'run' + r.split('.')[0][-4:])

    df['N_fil'] /= 1000.0
    df['N_crs'] /= 1000.0
    df['N_myo'] /= 1000.0

    condition0 = sorted(df['N_fil'].unique())
    condition1 = sorted(df['N_crs'].unique())
    condition2 = sorted(df['N_myo'].unique())
    frames = range(1000)

    for c0 in condition0:
        T = []
        r = df.query('N_fil==@c0')

        for ix, r in r.iterrows():
            crs = r['N_crs']
            myo = r['N_myo']
            run = r['run']
            for f in frames:
                im_path = f"{cytosim_lst.parent}/{run}/movie{f:04d}.png"
                T.append({'crs':     crs,
                          'myo':     myo,
                          'frame':   f,
                          'picture': im_path,
                          })
        ph = pd.DataFrame(T)


    async def render_frame(frame, result_queue):
        print(f"rendering frame {frame}")

        # render grid
        fdf = ph.query("frame==@frame")

        grid = sns.FacetGrid(fdf, row='crs', col='myo', height=1, aspect=1, margin_titles=True, despine=True)
        grid.map(lambda x, **kwargs: (plt.imshow(imageio.imread(x.values[0])), plt.grid(False)), 'picture')
        grid.set_xlabels("")
        grid.set(xticks=[], yticks=[])
        grid.set_titles(row_template="{row_var} {row_name}k", col_template="{col_var} {col_name}k")
        grid.fig.suptitle(f"{int(c0 * 1000)} filaments")
        grid.tight_layout()
        grid.fig.subplots_adjust(wspace=0, hspace=0)
        img = mplfig_to_npimage(grid.figure)  # RGB image of the figure

        imageio.imwrite(f"tmp/f{frame:05d}.png", img)

        plt.close(grid.figure)
        del img, grid, fdf

        await result_queue.put(f"finished render of frame {frame}")


    def make_frame_mpl(t):
        global _last_f, _render
        # calculate frame given time
        frame = int(fps * t)

        if frame == _last_f:
            return _render

        _render = imageio.imread(f"tmp/f{frame:05d}.png")
        _last_f = frame
        return _render


    # initialization parameters
    fps = 25
    n_frames = 1000
    duration = n_frames / fps

    # pre-draw images
    ensure_dir("tmp")
    print("Pre-rendering frames...")


    async def result_reader(queue):
        while True:
            value = await queue.get()
            if value is None:
                break
            print("Got value! -> {}".format(value))


    async def run():
        result_queue = asyncio.Queue()
        reader_future = asyncio.ensure_future(result_reader(result_queue), loop=loop)

        # Start a worker pool with 10 coroutines, invokes `render_frame` and waits for it to complete.
        async with asyncpool.AsyncPool(loop, num_workers=multiprocessing.cpu_count(),
                                       name="RenderPool",
                                       logger=logging.getLogger("RenderPool"),
                                       worker_co=render_frame,
                                       log_every_n=10) as pool:
            for i in frames:
                await pool.push(i, result_queue)

        await result_queue.put(None)
        await reader_future


    loop = asyncio.get_event_loop()
    loop.run_until_complete(run())

    # Start of video render method
    filename = "test.cytosim.mp4"

    animation = VideoClip(make_frame_mpl, duration=duration)
    animation.write_videofile(filename, fps=fps, bitrate="20M")
    animation.close()
    shutil.rmtree('tmp', ignore_errors=False, onerror=None)
