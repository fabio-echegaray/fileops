import yaml


class ParameterMixin:
    log = None

    def __init__(self, parameter_filename="config.yml", parameter_filter_dict=None, parameter_prefix=None, **kwargs):
        self.log.info(f"Loading parameters from {parameter_filename}.")
        self._pfname = parameter_filename
        self.prefix = parameter_prefix  # string to prefix to all parameters extracted from file

        with open(self._pfname, "r") as ymlfile:
            yml_params = yaml.load(ymlfile)

        self._filter_params = None
        # filter the yaml file to get the right section
        if parameter_filter_dict is None:
            self._filter_params = yml_params
        else:
            for section in yml_params:
                self.log.debug(f'Looking parameters in {section} section.')
                # check if items of filter are identical to the items in the file
                if all(item in yml_params[section].items() for item in parameter_filter_dict.items()):
                    self.log.info(f'Parameters found in section {section}.')
                    self._filter_params = yml_params[section]
                    break

        super().__init__(**kwargs)

    def __getattr__(self, name):
        if self._filter_params is None:
            return None
        if name[:len(self.prefix)] == self.prefix:
            search_name = name[len(self.prefix) + 1:]
            if search_name in self._filter_params:
                return self._filter_params[search_name]
        raise AttributeError(f"No attribute found with the name '{name}'.")

    # def get_parameter(self, parameter):
    #     if parameter in self._filter_params:
    #         return self._filter_params[parameter]
    #     return None
