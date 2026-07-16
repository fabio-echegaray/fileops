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
            param_override.frames = _parse_ranges(_frame, img_file.n_frames)
        except ValueError as e:
            log.error(f"error parsing frames in section {section}")
            pass

    # check if channel data is in the specific SECTION of the configuration file
    _ch_lbl = "channel" if "channel" in section else "channels" if "channels" in section else None
    if _ch_lbl is not None:
        try:
            _channel = section[_ch_lbl]
            param_override.channels = _parse_ranges(_channel, img_file.n_channels)
        except ValueError as e:
            pass

    # check if zstack data is in the configuration file
    _z_lbl = "zstack" if "zstack" in section else "zstacks" if "zstacks" in section else None
    if "zstack" in section:
        try:
            _z = section[_z_lbl]
            param_override.zstacks = _parse_ranges(_z, img_file.n_zstacks)
        except ValueError as e:
            pass

    # check if there is a specific frame to reference
    if "reference_frame" in section:
        ref_fr = int(section["reference_frame"])
        param_override.reference_frame = ref_fr

    return param_override


# ----------------------------------------------------------------------------------------------------------------------
#  internal utility routines to parse numeral arguments
# ----------------------------------------------------------------------------------------------------------------------
def _parse_ranges(range_txt: str, of_n: int):
    if range_txt == "all":
        return range(of_n)
    elif ".." in range_txt:
        _s = range_txt.split("..")
        return range(int(_s[0]), int(_s[1]) + 1)
    elif range_txt[0] == "[" and range_txt[-1] == "]":
        return sorted(ast.literal_eval(range_txt))
    else:
        return [int(range_txt)]
