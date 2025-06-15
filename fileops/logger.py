import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

log_dict = dict()
handlers = dict()
_formatter = logging.Formatter('[%(asctime)s] %(levelname)s %(name)s - %(message)s')


class LogMixin:
    def __init__(self, name, log_path=None, debug=True, formatter=_formatter):
        if name in log_dict:
            self.logger = log_dict[name]
        else:
            self.logger = logging.getLogger(name)
            log_dict[name] = self.logger

        if log_path is None:
            log_path = Path('.')

        pd.set_option('display.width', 1000)
        pd.set_option('display.max_rows', 50)
        pd.set_option('display.max_columns', 500)
        pd.set_option('display.max_colwidth', 100)
        np.set_printoptions(1)

        logging.getLogger('py.warnings').setLevel(logging.ERROR)

        # create file handler and set level to info
        ch = logging.FileHandler(log_path / 'console.log')
        ch.setFormatter(formatter)
        ch.setLevel(logging.DEBUG if debug else logging.INFO)

        for component_log in [name, 'shapely', 'matplotlib', 'mpl_events', 'xmlschema', 'Thread-0', '[Thread-0]']:
            lgr = logging.getLogger(component_log)
            lgr.addHandler(ch)
            if component_log != name:
                lgr.setLevel(logging.INFO)


def get_logger(*args, debug=True, name="default", log_path=None, formatter=_formatter):
    if len(args) == 1 and name == "default":
        name = args[0]
    logging.basicConfig(level=logging.DEBUG if debug else logging.INFO, stream=sys.stdout)
    log = LogMixin(name, log_path=log_path, debug=debug, formatter=formatter)

    return log.logger


def silence_loggers(loggers=None, output_log_file=None, debug=True, formatter=_formatter):
    if loggers is None:
        loggers = []
    if type(loggers) == str:
        loggers = [loggers]

    for name in loggers:
        if name not in log_dict:
            lgr = logging.getLogger(name)
            lgr.propagate = False
            lgr.setLevel(logging.DEBUG if debug else logging.INFO)
            log_dict[name] = lgr

    if output_log_file:
        # create file handler and set level to info
        ch = logging.FileHandler(output_log_file)
        ch.setFormatter(formatter)
        for name in loggers:
            lgr = log_dict[name]
            if name not in handlers:
                handlers[name] = ch
                lgr.addHandler(ch)
