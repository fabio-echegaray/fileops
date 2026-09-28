import ast
from pathlib import Path

import configparser

from fileops.image import ImageFile
from fileops.logger import get_logger

log = get_logger(name='export')

_INLINE_COMMENT_PREFIXES = "#;"


def _strip_inline_comments(line: str) -> str:
    """Strip a trailing inline comment, but never at the expense of the value.

    Vanilla ``ConfigParser(inline_comment_prefixes=('#', ';'))`` reads the ``#``
    in ``color = #4fff09`` as an inline comment and silently empties the value.
    Here a prefix only starts an inline comment when a non-blank value precedes
    it, so hex colors survive while ``color = (1, 0, 1, 0) # green`` still keeps
    only ``(1, 0, 1, 0)``.  Full-line comments are left for ConfigParser's own
    comment handling.
    """
    delim = None
    for i, ch in enumerate(line):
        if ch in "=:":
            delim = i
            break
    if delim is None:
        return line  # no key/value delimiter (section header, comment, continuation)

    cut = None
    for i in range(delim + 1, len(line)):
        if line[i] in _INLINE_COMMENT_PREFIXES and (i == 0 or line[i - 1].isspace()) \
                and line[delim + 1:i].strip():
            cut = i
            break
    if cut is None:
        return line
    body = line[:cut]
    for eol in ("\r\n", "\n"):
        if line.endswith(eol):
            return body + eol
    return body


def read_cfg_into(cfg: configparser.ConfigParser, path: Path) -> None:
    """Read a configuration file into *cfg*, stripping inline comments.

    ``read_cfg_into`` replaces ``cfg.read(path)`` here and in the config
    readers: it reproduces ConfigParser's inline-comment handling but protects
    values that start with a comment character (e.g. `` color = #4fff09``) from
    being eaten.
    """
    text = Path(path).read_text(encoding="utf-8", errors="surrogateescape")
    cleaned = "".join(_strip_inline_comments(line) for line in text.splitlines(keepends=True))
    cfg.read_string(cleaned, source=str(path))


def read_defaults_into_cfg(cfg: configparser.ConfigParser, defaults_file: Path | list[Path]):
    """Read one or more defaults files into a ConfigParser.

    When a list is provided, files are read furthest-first so that the
    closest file to the config file takes priority (its values override
    those of files read earlier).
    """
    if isinstance(defaults_file, Path):
        if not defaults_file.exists():
            raise FileNotFoundError(f"Defaults file {defaults_file} does not exist!")
        read_cfg_into(cfg, defaults_file)
    elif isinstance(defaults_file, list):
        for df in reversed(defaults_file):
            if not df.exists():
                raise FileNotFoundError(f"Defaults file {df} does not exist!")
            read_cfg_into(cfg, df)


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
            log.error(f"error parsing frames in section {section}: {e}")

    # check if channel data is in the specific SECTION of the configuration file
    _ch_lbl = "channel" if "channel" in section else "channels" if "channels" in section else None
    if _ch_lbl is not None:
        try:
            _channel = section[_ch_lbl]
            param_override.channels = _parse_ranges(_channel, img_file.n_channels)
        except ValueError as e:
            log.error(f"error parsing channels in section {section}: {e}")

    # check if zstack data is in the configuration file
    _z_lbl = "zstack" if "zstack" in section else "zstacks" if "zstacks" in section else None
    if "zstack" in section:
        try:
            _z = section[_z_lbl]
            param_override.zstacks = _parse_ranges(_z, img_file.n_zstacks)
        except ValueError as e:
            log.warning(f"ignoring non-numeric zstack override in section {section}: {e}")
            param_override.zstacks = range(img_file.n_zstacks)

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
