import os
from pathlib import Path

import yaml


class ParameterMixin:
    log = None

    def __init__(self, parameter_filename="config.yml", parameter_prefix=None, **kwargs):
        self.log.info(f"Loading parameters from {parameter_filename}.")
        self._pfname = parameter_filename
        self.prefix = parameter_prefix  # string to prefix to all parameters extracted from file
        self.section = None

        if os.path.exists(self._pfname):
            with open(self._pfname, "r") as ymlfile:
                self.sections = yaml.safe_load(ymlfile)

        super().__init__(**kwargs)

    def __getattr__(self, name):
        if self.section is None:
            return None
        if name[:len(self.prefix)] == self.prefix:
            search_name = name[len(self.prefix) + 1:]
            if search_name in self.sections[self.section]:
                return self.sections[self.section][search_name]
        raise AttributeError(f"No attribute found with the name '{name}'.")

    @property
    def configfile_path(self):
        return Path(self._pfname)

    def get_section(self, parameter_filter_dict=None):
        # filter the yaml file to get the right section
        if parameter_filter_dict is not None:
            for section in self.sections:
                if section == 'general':
                    continue
                self.log.debug(f'Looking parameters in {section} section.')
                # check if items of filter are identical to the items in the file
                if all(item in self.sections[section].items() for item in parameter_filter_dict.items()):
                    self.log.info(f'Parameters found in section {section}.')
                    self.section = section

                    # out = copy.deepcopy(self)
                    # out._pfname = None
                    # out.sections = self.sections[section]
                    return self.sections[section]
