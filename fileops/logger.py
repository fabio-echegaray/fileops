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
            self.logger.setLevel(logging.DEBUG if debug else logging.INFO)

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

        logging.getLogger('shapely').setLevel(logging.INFO)
        logging.getLogger('matplotlib').setLevel(logging.INFO)
        logging.getLogger('mpl_events').setLevel(logging.INFO)
        logging.getLogger('Thread-0').setLevel(logging.INFO)
        logging.getLogger('[Thread-0]').setLevel(logging.INFO)


def get_logger(*args, debug=True, name="default"):
    if len(args) == 1 and name == "default":
        name = args[0]
    logging.basicConfig(level=logging.DEBUG if debug else logging.INFO, stream=sys.stdout)
    log = LogMixin(name, debug=debug)

    return log.logger
