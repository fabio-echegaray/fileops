import sys
import logging

import pandas as pd
import numpy as np

log_dict = dict()


class LogMixin:
    def __init__(self, name, debug=True):
        if name in log_dict:
            self.logger = log_dict[name]
        else:
            self.logger = logging.getLogger(name)

            # console = logging.StreamHandler(sys.stdout)
            # formatter = logging.Formatter('%(name)-12s: %(levelname)-8s %(message)s')
            # console.setFormatter(formatter)
            # self.logger.addHandler(console)
            log_dict[name] = self.logger

        pd.set_option('display.width', 1000)
        pd.set_option('display.max_rows', 50)
        pd.set_option('display.max_columns', 500)
        pd.set_option('display.max_colwidth', 100)
        np.set_printoptions(1)

        logging.getLogger('py.warnings').setLevel(logging.ERROR)

        # create file handler and set level to info
        ch = logging.FileHandler('console.log')
        ch.setLevel(logging.DEBUG if debug else logging.INFO)

        for component_log in [name, 'shapely', 'matplotlib', 'mpl_events', 'xmlschema', 'Thread-0', '[Thread-0]']:
            lgr = logging.getLogger(component_log)
            lgr.addHandler(ch)
            if component_log != name:
                lgr.setLevel(logging.INFO)


def get_logger(*args, debug=True, name="default"):
    if len(args) == 1 and name == "default":
        name = args[0]
    logging.basicConfig(level=logging.DEBUG if debug else logging.INFO, stream=sys.stdout)
    log = LogMixin(name, debug=debug)

    return log.logger


def silence_loggers(loggers=None, output_log_file=None, debug=True):
    if loggers is None:
        loggers = []
    if output_log_file:
        # create file handler and set level to info
        ch = logging.FileHandler(output_log_file)
        ch.setLevel(logging.DEBUG if debug else logging.INFO)
    for logger in loggers:
        lgr = logging.getLogger(logger)
        lgr.propagate = False
        if output_log_file:
            lgr.addHandler(ch)
