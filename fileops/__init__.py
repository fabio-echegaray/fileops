import multiprocessing
import os
import sys
import threading

from fileops.logger import get_logger

# flag for when background threads should stop (second Ctrl-C / SIGTERM)
__THREAD_STOP_REQUESTED = threading.Event()

# flag for when the folder loop should stop after current work (first Ctrl-C)
__STOP_REQUESTED = threading.Event()

# state of multiprocess z-projection
_manager = None
__s_lock, __s_dict, __s_list, __s_sem = None, None, None, None


def init_shared_state():
    """Initializes the manager and shared objects.
    Must be called exactly once from the __main__ block of the main script.
    """
    global _manager, __s_lock, __s_dict, __s_list, __s_sem

    if _manager is None:
        # Create the manager explicitly when called
        _manager = multiprocessing.Manager()
        __s_lock = _manager.Lock()
        __s_dict = _manager.dict()
        __s_list = _manager.list()
        __s_sem = _manager.Semaphore(os.cpu_count())


def get_shared_state():
    global _manager, __s_lock, __s_dict, __s_list, __s_sem

    if _manager is None:
        init_shared_state()

    return __s_lock, __s_dict, __s_list, __s_sem


def reset_shared_state():
    """Clears the shared state between renders so stale cache entries don't persist."""
    if __s_dict is not None:
        __s_dict.clear()
    if __s_list is not None:
        del __s_list[:]


# check for plugins
if sys.version_info < (3, 10):
    from importlib_metadata import entry_points
else:
    from importlib.metadata import entry_points

log = get_logger(name='fileops-plugin-engine')

# load all types
config_type_plugins = entry_points(group='fileops.plugins.config.types')
for dp in config_type_plugins:
    log.info(f"found plugin for header {dp.name} ({dp.value})")

header_reader_plugins = entry_points(group='fileops.plugins.config.header_readers')
log.info(f"Found {len(header_reader_plugins)} configuration section parsers. ({[hr.name for hr in header_reader_plugins]})")
