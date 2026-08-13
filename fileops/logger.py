import logging
import sys
import time

import numpy as np
import pandas as pd
import verboselogs

verboselogs.install()

log_dict = dict()
handlers = dict()
_formatter = logging.Formatter('[%(asctime)s] %(levelname)s %(name)s - %(message)s')


def _legacy_formatting():
    pd.set_option('display.width', 1000)
    pd.set_option('display.max_rows', 50)
    pd.set_option('display.max_columns', 500)
    pd.set_option('display.max_colwidth', 100)
    np.set_printoptions(1)

    logging.getLogger('py.warnings').setLevel(logging.ERROR)


class SummarizingFilter(logging.Filter):
    def __init__(self, max_wait_time=10):
        super().__init__()
        self.last_message = None
        self.repeat_count = 0
        self.last_log = time.time()
        self._wait_time = max_wait_time

    def filter(self, record):
        message = record.getMessage()
        now = time.time()
        too_much_time = (now - self.last_log) > self._wait_time
        if message == self.last_message:
            if too_much_time:
                summary = f'({self.last_message}) repeated {self.repeat_count} times'
                record.msg = summary
                self.repeat_count = 0
                self.last_log = now
                return True

            self.repeat_count += 1
            return False  # Suppress
        else:
            if self.repeat_count > 0:
                # Log a summary of the repeated message
                summary = f'({self.last_message}) repeated {self.repeat_count} times'
                record.msg = f'{summary}\r\n{record.msg}'
            self.last_message = message
            self.repeat_count = 0
            self.last_log = now
            return True  # Allow


class LogMixin:
    def __init__(self, name, debug=True, summarize=True, formatter=_formatter):
        if name in log_dict:
            self.logger = log_dict[name]
        else:
            self.logger = logging.getLogger(name)
            if summarize:
                self.logger.addFilter(SummarizingFilter())
            log_dict[name] = self.logger


def get_logger(*args, debug=True, summarize=False, name="default", log_path=None, formatter=_formatter):
    # since log_path is deprecated, assume the old formatting is expected
    if log_path is not None:
        _legacy_formatting()

    if len(args) == 1 and name == "default":
        name = args[0]
    logging.basicConfig(level=logging.DEBUG if debug else logging.INFO, stream=sys.stdout)
    log = LogMixin(name, debug=debug, summarize=summarize, formatter=formatter)

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
