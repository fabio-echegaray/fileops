import asyncio
import logging
import multiprocessing
import os
import shutil
from pathlib import Path

import asyncpool
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


def render_last_frame(df: pd.DataFrame):
    df['N_fil'] /= 1000.0
    df['N_crs'] /= 1000.0
    df['N_myo'] /= 1000.0

    condition0 = sorted(df['N_fil'].unique())
    condition1 = sorted(df['N_crs'].unique())
    condition2 = sorted(df['N_myo'].unique())

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
    # build dataframe of images
    print("Reading dataframe...")
    cytosim_fld = '/media/lab/Data/Fabio/Dev/Python-actomyosin-furrows/cytosim/'
    cytosim_lst = Path(f'{cytosim_fld}/actomyosin_sweep/treadmill/simulations.csv')
    df = (pd.read_csv(cytosim_lst, skipinitialspace=True)
          .drop(columns='n')
          # .query("N_fil==5000")
          )
    df['run'] = df['file'].apply(lambda r: 'run' + r.split('.')[0][-4:])

    render_last_frame(df)
