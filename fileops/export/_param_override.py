import ast
from typing import Set, Tuple, Any

import matplotlib.colors as mcolors
from fileops.image import ImageFile
from fileops.logger import get_logger

log = get_logger(name='export')

_ch_info_structure = {
    "name":      "default",
    "color":     "magenta",
    "histogram": False,
}


class ParameterOverride:
    dt: float = None
    frames: Set
    channels: Set
    zstacks: Set

    def __init__(self, image_file: ImageFile):
        self._frames = set(image_file.frames)
        self._channels = set(image_file.channels)
        self._channel_info = dict()
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
        """The setter for the 'data' attribute, expecting a key-value pair."""
        try:
            v_set = set(list(value))
            self._channels = self._channels.intersection(v_set)
        except Exception as e:
            log.error(e)

    @property
    def channel_info(self):
        return self._channel_info

    @channel_info.setter
    def channel_info(self, value: Tuple[int, Any]):
        # validation of the input structure
        if isinstance(value, tuple) and len(value) == 2:
            ch_key, item = value
            # You can add validation or custom logic here
            if not isinstance(ch_key, int):
                raise TypeError("Key must be an integer.")
            if not isinstance(item, (dict,)):
                raise ValueError("Value must be a dictionary of values.")
        else:
            raise ValueError("Setter for 'data' expects a (key, value) tuple.")

        # validation of the parameters
        if len(item.keys()) > 3:
            raise IndexError("Channel info structure does not support more than the "
                             "following attributes: ['name', 'color', 'histogram'].")
        if "name" in item and type(item["name"]) != str:
            raise TypeError("Name property must be a string.")
        for _c in ["color", "colour"]:
            if _c in item:
                # Check if a value is color-like
                color = item[_c]
                if isinstance(color, str) and "(" in color and ")" in color:  # the string is likely encoding a tuple
                    color = ast.literal_eval(color)
                is_valid_color = mcolors.is_color_like(color)
                if not is_valid_color:
                    raise TypeError(f"Color definition {color} for channel {ch_key} is invalid.")
                item[_c] = color
        if "histogram" in item:
            item["histogram"] = bool(item["histogram"]) if type(item["histogram"]) in (int, bool) else \
                True if type(item["histogram"]) == str and item["histogram"] == "yes" else False

        if ch_key in self._channel_info:
            self._channel_info[ch_key].update(item)
        else:
            template_ch_info = _ch_info_structure.copy()
            template_ch_info.update(item)
            self._channel_info[ch_key] = template_ch_info

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
