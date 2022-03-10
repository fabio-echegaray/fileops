import argparse
import logging
import os

import javabridge
import pandas as pd
import numpy as np

from cached import CachedImageFile
from fileops.image.mmanager import MicroManagerFolderSeries
from movielayouts.single import make_movie

from logger import get_logger
from pathutils import ensure_dir

log = get_logger(name='summary')
logging.getLogger('movierender').setLevel(logging.INFO)


def process_dir(path, out_folder='.') -> pd.DataFrame:
    out = pd.DataFrame()
    for root, directories, filenames in os.walk(path):
        for filename in filenames:
            ext = filename.split('.')[-1]
            ini = filename[0]
            if ext == 'mvd2' and ini != '.':
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
                                       folder=out_folder)
                except FileNotFoundError as e:
                    log.warning(f'Data not found for file {joinf}.')
                except AssertionError as e:
                    log.error(f'Error trying to render file {joinf}.')
                    log.error(e)

            elif ext == 'tif' and ini != '.':
                try:
                    if MicroManagerFolderSeries.has_valid_format(root):  # folder is full of tif files
                        log.info(f'Processing folder {root}')
                        img_struc = MicroManagerFolderSeries(root)
                        out = out.append(img_struc.info, ignore_index=True)
                        # make movie
                        for s in img_struc.all_positions:
                            img_struc.series = s
                            if len(img_struc.frames) > 1:
                                make_movie(img_struc,
                                           suffix='-' + img_struc.position_md['Label'],
                                           folder=out_folder)
                        break  # skip the rest of the files in the folder
                except FileNotFoundError as e:
                    log.warning(f'Data not found in folder {root}.')
                except AssertionError as e:
                    log.error(f'Error trying to render images from folder {root}.')
                    log.error(e)

    return out


if __name__ == '__main__':
    description = 'Generate pandas dataframe summary of microscope images stored in the specified path (recursively).'
    epilogue = '''
    The outputs are two files in Excel and comma separated values (CSV) formats, i.e., summary.xlsx and summary.csv.
    '''
    parser = argparse.ArgumentParser(description=description, epilog=epilogue,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('path', help='Path where to start the search.')
    parser.add_argument(
        '--out-dir', action='store', default='./movies',
        help="Output folder where the movies will be saved.",
        type=str, dest='out'
    )
    args = parser.parse_args()
    ensure_dir(os.path.abspath(args.out))

    xls = pd.read_excel('summary.xlsx')
    print(xls)

    df = process_dir(args.path, args.out)
    df.to_excel('summary-new.xlsx', index=False)
    print(df)
    merge = pd.merge(xls, df, how='outer',
                     on=['filename', 'instrument_id', 'pixels_id', 'channels', 'z-stacks', 'frames'])
    merge.to_excel('summary-merge.xlsx', merge_cells=True)

    # fname = '/media/lab/Data/Fabio/Zeiss/20210914 - SqhGFP/20210914 - SqhGFP.mvd2'
    # cif = CachedImageFile(fname, cache_results=False)
    # cif.series = cif.all_series[1]
    # cif.timestamps = cif.frames * 60
    # print(cif.timestamps)
    # print(cif.frames)
    # make_movie(cif,
    #            suffix='-' + cif.series.attrib['ID'].replace(':', ''),
    #            folder=ensure_dir('/media/lab/Data/Fabio/movies/sneakpeek'))

    javabridge.kill_vm()
