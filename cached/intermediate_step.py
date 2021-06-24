import os
import pickle

from logger import get_logger

log = get_logger(name='cached_ops')


def cached_step(filename, function, *args, cache_folder=None, override_cache=False, **kwargs):
    cache_folder = os.path.abspath(".") if cache_folder is None else cache_folder
    output_path = os.path.join(cache_folder, filename)
    if not os.path.exists(output_path) or override_cache:
        log.debug(f"Generating data for step that calls function {function.__name__}.")
        out = function(*args, **kwargs)
        log.debug(f"Saving object {filename} in cache (path={output_path}).")
        if override_cache:
            with open(output_path, 'wb') as f:
                pickle.dump(out, f)
        return out
    else:
        log.debug(f"Loading object {filename} from cache (path={output_path}).")
        with open(output_path, 'rb') as f:
            obj = pickle.load(f)
        return obj
