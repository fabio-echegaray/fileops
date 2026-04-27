import configparser
from pathlib import Path
from typing import Dict

from fileops.export.config_data_section import read_data_section
from fileops.plugins.base_plugin import BaseFileOpsPlugin


class HeaderReaderPlugin(BaseFileOpsPlugin):
    def __init__(self, config_file_path: Path, root_path: Path = None, **kwargs):
        super().__init__()
        self._headers = None
        self._cfg_path = config_file_path
        self._root_path = root_path
        self.__cfg, self.__imf, self.__povrr, self.__roi = None, None, None, None

    def _load_data_section(self):
        rp = self._root_path
        self.__cfg, self.__imf, self.__povrr, self.__roi = read_data_section(self._cfg_path, with_root_path=rp)

    @property
    def _cfg(self):
        if self.__cfg is None:
            self.__cfg = configparser.ConfigParser()
            self.__cfg.read(self._cfg_path)
        return self.__cfg

    @property
    def _img_file(self):
        if self.__imf is None:
            self._load_data_section()
        return self.__imf

    @property
    def _param_override(self):
        if self.__povrr is None:
            self._load_data_section()
        return self.__povrr

    @property
    def _roi(self):
        if self.__roi is None:
            self._load_data_section()
        return self.__roi

    def has_valid_header(self):
        raise NotImplementedError

    def header_output_file_exist(self) -> Dict[str, bool]:
        """ check if output file paths exists while loading the minimum required structure """
        raise NotImplementedError

    @staticmethod
    def generate(file, *args, **kwargs):
        raise NotImplementedError
