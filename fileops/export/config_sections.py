import ast

from fileops.image import ImageFile
from fileops.logger import get_logger

log = get_logger(name='export')


# ----------------------------------------------------------------------------------------------------------------------
#  routines that override parameters in subsequent sections of the config file
# ----------------------------------------------------------------------------------------------------------------------
def process_overrides_of_section(section, param_override, img_file: ImageFile):
    # override frames if defined again in section
    # check if frame data is in the configuration file
    _fr_lbl = [l for l in section.keys() if l[:5] == "frame"]
    if len(_fr_lbl) == 1:
        _fr_lbl = _fr_lbl[0]
        try:
            _frame = section[_fr_lbl]
            if _frame == "all":
                param_override.frames = range(img_file.n_frames)
            elif ".." in _frame:
                _f = _frame.split("..")
                param_override.frames = range(int(_f[0]), int(_f[1]) + 1)
            elif _frame[0] == "[" and _frame[-1] == "]":
                param_override.frames = sorted(ast.literal_eval(_frame))
            else:
                param_override.frames = [int(_frame)]
        except ValueError as e:
            log.error(f"error parsing frames in section {section}")
            pass

    # check if channel data is in the configuration file
    _ch_lbl = "channel" if "channel" in section else "channels" if "channels" in section else None
    if _ch_lbl is not None:
        try:
            _channel = section[_ch_lbl]
            param_override.channels = range(img_file.n_channels) if _channel == "all" else [int(_channel)]
        except ValueError as e:
            pass

    # check if zstack data is in the configuration file
    _z_lbl = "zstack" if "zstack" in section else "zstacks" if "zstacks" in section else None
    if "zstack" in section:
        try:
            _z = section[_z_lbl]
            param_override.zstacks = range(img_file.n_zstacks) if _z == "all" else [int(_z)]
        except ValueError as e:
            pass

    return param_override
