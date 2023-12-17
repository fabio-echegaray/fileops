import os
import argparse
import logging
from pathlib import Path
import traceback

import javabridge
import pandas as pd

from fileops.image import MicroManagerFolderSeries
from fileops.image.factory import load_image_file
from movielayouts.two_ch_composite import make_movie

from logger import get_logger
from pathutils import ensure_dir

log = get_logger(name='summary')
logging.getLogger('movierender').setLevel(logging.INFO)


def process_dir(path, out_folder='.', render_movie=True) -> pd.DataFrame:
    out = pd.DataFrame()
    r = 1
    files_visited = []
    for root, directories, filenames in os.walk(path):
        for filename in filenames:
            joinf = 'No file specified yet'
            try:
                joinf = Path(root) / filename
                log.info(f'Processing {joinf.as_posix()}')
                if joinf not in files_visited:
                    img_struc = load_image_file(joinf)
                    if img_struc is None:
                        continue
                    out = out.append(img_struc.info, ignore_index=True)
                    files_visited.extend([Path(root) / f for f in img_struc.files])
                    r += 1
                    # make movie
                    if render_movie:
                        if len(img_struc.frames) > 1:
                            p = Path(img_struc.info['folder'].values[0])
                            pos = p.name
                            make_movie(img_struc, prefix=f'r{r:02d}-{pos}',
                                       suffix='-' + img_struc.info['filename'].values[0],
                                       folder=out_folder)
                    if type(img_struc) == MicroManagerFolderSeries:  # all files in the folder are of the same series
                        break
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

    df = process_dir(args.path, args.out, render_movie=True)
    df.to_excel('summary-new.xlsx', index=False)
    print(df)

    javabridge.kill_vm()
