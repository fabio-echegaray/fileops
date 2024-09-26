import os
import argparse
import logging
from pathlib import Path
import traceback

import pandas as pd

from fileops.image import MicroManagerFolderSeries
from fileops.image.factory import load_image_file

from fileops.pathutils import ensure_dir
from fileops.logger import get_logger, silence_loggers

log = get_logger(name='summary')


def process_dir(path) -> pd.DataFrame:
    out = pd.DataFrame()
    r = 1
    files_visited = []
    silence_loggers(loggers=["tifffile"], output_log_file="silenced.log")
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
                    out = pd.concat([out, img_struc.info], ignore_index=True)
                    files_visited.extend([Path(root) / f for f in img_struc.files])
                    r += 1
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
    args = parser.parse_args()
    # ensure_dir(os.path.abspath(args.out))

    df = process_dir(args.path)
    df.to_excel('summary-new.xlsx', index=False)
    print(df)
