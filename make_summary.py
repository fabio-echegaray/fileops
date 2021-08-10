import logging
import os
import argparse
import javabridge

import pandas as pd

import matplotlib.pyplot as plt

from cached import CachedImageFile

import movierender.overlays as ovl
from movierender import MovieRenderer
from movierender.render.pipelines import SingleImage

from logger import get_logger

log = get_logger(name='summary')
logging.getLogger('movierender').setLevel(logging.INFO)


def make_movie(im: CachedImageFile, suffix='', folder='.'):
    log.info(f'Making movies of file {os.path.basename(im.image_path)}')

    filename = os.path.basename(im.image_path) + suffix + ".mp4"
    base_folder = os.path.abspath(folder)

    log.info(f'Making movie {filename} in folder {base_folder}')

    fig = plt.figure(frameon=False, figsize=(5, 5), dpi=150)
    movren = MovieRenderer(image=im,
                           fig=fig,
                           fps=15,
                           show_axis=True,
                           bitrate="10M",
                           fontdict={'size': 12}) + \
             ovl.ScaleBar(um=10, lw=3, xy=(140, 5), fontdict={'size': 9}) + \
             ovl.Timestamp(xy=(1, 160), string_format="mm:ss", va='center') + \
             SingleImage()
    movren.render(filename=os.path.join(base_folder, filename), test=False)


def process_dir(path) -> pd.DataFrame:
    out = pd.DataFrame()
    for root, directories, filenames in os.walk(path):
        for filename in filenames:
            ext = filename.split('.')[-1]
            if ext == 'mvd2':
                try:
                    joinf = os.path.join(root, filename)
                    log.info(f'Processing {joinf}')
                    img_struc = CachedImageFile(joinf, cache_results=False)
                    out = out.append(img_struc.info, ignore_index=True)
                    # make movie
                    for s in img_struc.all_series:
                        img_struc.series = s
                        if len(img_struc.frames) > 1:
                            make_movie(img_struc,
                                       suffix='-' + img_struc.series.attrib['ID'].replace(':', ''),
                                       folder='/media/lab/Data/Fabio/movies/sneakpeek')
                except FileNotFoundError as e:
                    log.warning(f'Data not found for file {joinf}.')

    return out


if __name__ == '__main__':
    description = 'Generate pandas dataframe summary of microscope images stored in the specified path (recursively).'
    epilogue = '''
    The outputs are two files in Excel and comma separated values (CSV) formats, i.e., summary.xlsx and summary.csv.
    '''
    parser = argparse.ArgumentParser(description=description, epilog=epilogue,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('path', help='Path where to start the search.')
    args = parser.parse_args()

    xls = pd.read_excel('summary.xlsx')
    print(xls)
    # exit()
    df = process_dir(args.path)
    df.to_excel('summary-orig.xlsx', index=False)
    print(df)
    merge = pd.merge(xls, df, how='outer',
                     on=['filename', 'instrument_id', 'pixels_id', 'channels', 'z-stacks', 'frames'])
    merge.to_excel('summary-merge.xlsx', merge_cells=True)

    javabridge.kill_vm()
