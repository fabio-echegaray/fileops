from pathlib import Path

from fileops.export.config_data_section import read_data_section
from fileops.plugins.base_plugin import BaseFileOpsPlugin


class HeaderReaderPlugin(BaseFileOpsPlugin):
    def __init__(self, config_file_path: Path):
        super().__init__()
        self._headers = None
        self._cfg_path = config_file_path
        self._cfg, self._img_file, self._param_override, self._roi = read_data_section(config_file_path)

    def has_valid_header(self):
        raise NotImplementedError

    @staticmethod
    def generate(file, *args, **kwargs):
        raise NotImplementedError
