import os
import argparse
import logging
import pathlib
import traceback

import javabridge
import pandas as pd

from cached import CachedImageFile
from fileops.image.mmanager import MicroManagerFolderSeries, MicroManagerImageStack, folder_is_micromagellan
from movielayouts.single import make_movie

from logger import get_logger
from pathutils import ensure_dir

log = get_logger(name='summary')
logging.getLogger('movierender').setLevel(logging.INFO)


def process_dir(path, out_folder='.', render_movie=True) -> pd.DataFrame:
    out = pd.DataFrame()
    r = 1
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
                    r += 1
                    # make movie
                    if render_movie:
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
                except BaseException as e:
                    log.error(e)
                    log.error(traceback.format_exc())
                    raise e

            elif ext == 'tif' and ini != '.' and not folder_is_micromagellan(root):
                try:
                    joinf = os.path.join(root, filename)
                    if MicroManagerFolderSeries.has_valid_format(root):  # folder is full of tif files
                        log.info(f'Processing folder {root}')
                        img_struc = MicroManagerFolderSeries(root)
                        out = out.append(img_struc.info, ignore_index=True)
                        r += 1
                        # make movie
                        if render_movie:
                            img_struc.series = img_struc.all_positions[0]
                            if len(img_struc.frames) > 1:
                                img_struc.frames = img_struc.frames[:100]
                                make_movie(img_struc, movie_name=f'r{r:02d}-' + img_struc.info['image_name'].values[0],
                                           suffix='-' + img_struc.info['image_id'].values[0],
                                           folder=out_folder)
                        break  # skip the rest of the files in the folder
                    if MicroManagerImageStack.has_valid_format(joinf):  # folder is full of tif files
                        log.info(f'Processing file {joinf}')
                        img_struc = MicroManagerImageStack(joinf)
                        out = out.append(img_struc.info, ignore_index=True)
                        r += 1
                        # make movie
                        if render_movie:
                            img_struc.series = img_struc.all_positions[0]
                            if len(img_struc.frames) > 1:
                                img_struc.frames = img_struc.frames[:100]
                                p = pathlib.Path(img_struc.info['folder'].values[0])
                                folder = p.parent.parent.name
                                pos = p.name
                                make_movie(img_struc, movie_name=f'r{r:02d}-{pos}',
                                           suffix='-' + img_struc.info['image_id'].values[0],
                                           folder=out_folder)
                except FileNotFoundError as e:
                    log.error(e)
                    log.warning(f'Data not found in folder {root}.')
                except (IndexError, KeyError) as e:
                    log.error(e)
                    log.warning(f'Data index/key not found in file; perhaps the file is truncated? (in file {joinf}).')
                except AssertionError as e:
                    log.error(f'Error trying to render images from folder {root}.')
                    log.error(e)
                except BaseException as e:
                    log.error(e)
                    log.error(traceback.format_exc())
                    raise e

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

    df = process_dir(args.path, args.out, render_movie=False)
    df.to_excel('summary-new.xlsx', index=False)
    print(df)

    javabridge.kill_vm()
