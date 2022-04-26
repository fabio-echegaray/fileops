import os
import pickle

from fileops.logger import get_logger
from fileops.pathutils import ensure_dir

log = get_logger(name='cached_ops')


def cached_step(filename, function, *args, cache_folder=None, override_cache=False, **kwargs):
    """
    Calls function with arguments args & kwargs and stores result in a file in the cache_folder folder.
    If the file is already in the folder, it loads the result instead.

    :param filename: Name of the file to store the result.
    :param function: Function to call.
    :param args: Position arguments to pass to the function.
    :param cache_folder: Folder to store the output of function.
    :param override_cache: Flag to overwrite the file in case it already exists.
    :param kwargs: Keyword arguments to pass to the function.
    :return: The (cached) object calculated by the function.
    """
    cache_folder = ensure_dir(os.path.abspath("") if cache_folder is None else cache_folder)
    output_path = os.path.join(cache_folder, filename)
    if not os.path.exists(output_path) or override_cache:
        log.debug(f"Generating data for step that calls function {function.__name__}.")
        out = function(*args, **kwargs)
        log.debug(f"Saving object {filename} in cache (path={output_path}).")
        try:
            with open(output_path, 'wb') as f:
                pickle.dump(out, f)
        except IOError as e:
            log.error(e)
        return out
    else:
        log.debug(f"Loading object {filename} from cache (path={output_path}).")
        try:
            with open(output_path, 'rb') as f:
                obj = pickle.load(f)
        except (pickle.UnpicklingError, EOFError) as e:
            log.error(e)

            log.info("Deleting file")
            f.close()
            os.remove(output_path)

            log.info("Re-trying calculation")
            obj = function(*args, **kwargs)
        return obj
