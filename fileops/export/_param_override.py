from typing import Set

from fileops.image import ImageFile
from fileops.logger import get_logger

log = get_logger(name='export')


class ParameterOverride:
    dt: float = None
    frames: Set
    channels: Set
    zstacks: Set

    def __init__(self, image_file: ImageFile):
        self._frames = set(image_file.frames)
        self._channels = set(image_file.channels)
        self._zstacks = set(image_file.zstacks)

    @property
    def frames(self):
        return self._frames

    @frames.setter
    def frames(self, value):
        try:
            v_set = set(list(value))
            self._frames = self._frames.intersection(v_set)
        except Exception as e:
            log.error(e)

    @property
    def channels(self):
        return self._channels

    @channels.setter
    def channels(self, value):
        try:
            v_set = set(list(value))
            self._channels = self._channels.intersection(v_set)
        except Exception as e:
            log.error(e)

    @property
    def zstacks(self):
        return self._zstacks

    @zstacks.setter
    def zstacks(self, value):
        try:
            v_set = set(list(value))
            self._zstacks = self._zstacks.intersection(v_set)
        except Exception as e:
            log.error(e)
