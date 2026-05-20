import sys

from fileops.logger import get_logger

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
