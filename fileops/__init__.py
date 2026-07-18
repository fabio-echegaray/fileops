import multiprocessing
import os
import sys
import threading

from fileops.logger import get_logger

# flag for when the concurrent system is finishing
__IS_EXITING = threading.Event()

# state of multiprocess z-projection
_manager = None
s_lock, s_dict, s_list, s_sem, s_lock = None, None, None, None, None


def init_shared_state():
    """Initializes the manager and shared objects.
    Must be called exactly once from the __main__ block of the main script.
    """
    global _manager, s_lock, s_dict, s_list, s_sem, s_lock

    if _manager is None:
        # Create the manager explicitly when called
        _manager = multiprocessing.Manager()
        s_lock = _manager.Lock()
        s_dict = _manager.dict()
        s_list = _manager.list()
        s_lock = _manager.Lock()
        s_sem = _manager.Semaphore(os.cpu_count())


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
