import configparser
from pathlib import Path
from typing import Dict

from fileops.export.config_data_section import read_data_section
from fileops.plugins.base_plugin import BaseFileOpsPlugin

# sentinel distinguishing "not provided" from "provided as None" (e.g. no ROI)
_UNSET = object()


class HeaderReaderPlugin(BaseFileOpsPlugin):
    def __init__(self, config_file_path: Path, root_path: Path = None, **kwargs):
        super().__init__()
        self._headers = None
        self._cfg_path = config_file_path
        self._root_path = root_path
        # Optional pre-loaded objects. When provided by read_config(), the media
        # file is opened once instead of once per plugin instance.
        self.__cfg = kwargs.get("cfg", _UNSET)
        self.__imf = kwargs.get("img_file", _UNSET)
        self.__povrr = kwargs.get("param_override", _UNSET)
        self.__roi = kwargs.get("roi", _UNSET)
        # Optional project-level defaults file whose [DEFAULT] section applies to all
        # sections of the configuration file.
        self._defaults_file = kwargs.get("defaults_file", _UNSET)

    def _load_data_section(self):
        rp = self._root_path
        df = None if self._defaults_file is _UNSET else self._defaults_file
        cfg, imf, povrr, roi = read_data_section(self._cfg_path, with_root_path=rp, defaults_file=df)
        # only fill the slots that were not provided, so pre-loaded objects are reused
        if self.__cfg is _UNSET:
            self.__cfg = cfg
        if self.__imf is _UNSET:
            self.__imf = imf
        if self.__povrr is _UNSET:
            self.__povrr = povrr
        if self.__roi is _UNSET:
            self.__roi = roi

    @property
    def _cfg(self):
        if self.__cfg is _UNSET:
            self.__cfg = configparser.ConfigParser()
            if self._defaults_file is not _UNSET and self._defaults_file is not None:
                self.__cfg.read(self._defaults_file)
            self.__cfg.read(self._cfg_path)
        return self.__cfg

    @property
    def _img_file(self):
        if self.__imf is _UNSET:
            self._load_data_section()
        return self.__imf

    @property
    def _param_override(self):
        if self.__povrr is _UNSET:
            self._load_data_section()
        return self.__povrr

    @property
    def _roi(self):
        if self.__roi is _UNSET:
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
