import traceback
from pathlib import Path
from typing import Union

from fileops.image import ImageFile, VolocityFile, MicroManagerFolderSeries, MicroManagerSingleImageStack
from fileops.image._pycromanager_single_stack import PycroManagerSingleImageStack
from fileops.logger import get_logger

log = get_logger(name='loading-factory')


def load_image_file(path: Path, **kwargs) -> Union[ImageFile, None]:
    ext = path.name.split('.')[-1]
    ini = path.name[0]
    img_file = None
    if ini == '.':
        return None
    try:
        if ext == 'mvd2':
            img_file = VolocityFile(path, **kwargs)
        elif ext == 'tif' or ext == 'tiff':
            if MicroManagerFolderSeries.has_valid_format(path.parent):  # folder is full of tif files
                log.info(f'Processing MicroManager folder {path.parent}')
                img_file = MicroManagerFolderSeries(path.parent, **kwargs)
            # let's try to open tiff file with PycroManager if available
            elif PycroManagerSingleImageStack.has_valid_format(path):
                log.info(f'Processing MicroManager file {path} using PycroManager')
                img_file = PycroManagerSingleImageStack(path, **kwargs)
            elif MicroManagerSingleImageStack.has_valid_format(path):
                log.info(f'Processing MicroManager file {path}')
                img_file = MicroManagerSingleImageStack(path, **kwargs)
    except FileNotFoundError as e:
        log.error(e)
        log.warning(f'Data not found in folder {path.parent}.')
        log.error(traceback.format_exc())
        img_file = None
    except (IndexError, KeyError) as e:
        log.error(e)
        log.warning(f'Data index/key not found in file; perhaps the file is truncated? (in file {path}).')
        log.error(traceback.format_exc())
    except AssertionError as e:
        log.error(f'Error trying to render images from folder {path.parent}.')
        log.error(e)
        log.error(traceback.format_exc())
    except BaseException as e:
        log.error(e)
        log.error(traceback.format_exc())
        raise e

    return img_file
