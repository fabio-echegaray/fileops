import configparser

from fileops.export._param_override import ParameterOverride
from fileops.logger import get_logger

log = get_logger(name='export')


# ----------------------------------------------------------------------------------------------------------------------
#  routines that override parameters in channel sections of the config file
# ----------------------------------------------------------------------------------------------------------------------
def update_overrides_from_channel_sections(param_override: ParameterOverride, cfg_path) -> ParameterOverride:
    cfg = configparser.ConfigParser()
    cfg.read(cfg_path)

    ch_sections = [s for s in cfg.sections() if "CHANNEL" in s]
    if len(ch_sections) == 0:
        log.info(f"No CHANNEL header in file {cfg_path}.")
        # generate default channel configuration
        for ch_num in param_override.channels:
            param_override.channel_info = (ch_num, dict(name=f"ch-{ch_num:02d}"))  # value has to be a tuple (key, dict)

        return param_override

    for ch_sec in ch_sections:
        ch_num = int(ch_sec.split("-")[1])
        section_data = cfg[ch_sec]
        # ch_key at this level is 1-indexed, but for at the level of ParameterOverride it's 0-indexed
        param_override.channel_info = (ch_num - 1, dict(section_data.items()))  # value has to be a tuple (key, dict)

    return param_override


def update_channel_config_with_section_overrides(param_override: ParameterOverride, sec) -> ParameterOverride:
    for key, val in sec.items():
        try:
            if key.startswith("channel"):
                _ch_keys = key.replace("gamma_", "gamma**").replace("rescale_", "rescale**").split("_")
                if len(_ch_keys) == 3:
                    k0, k1, k2 = _ch_keys
                    # channel number validation
                    ch_num = int(k1)
                    if ch_num < 1:
                        raise KeyError(f"Channel number in configuration file starts from 1.")
                    if k2 in ("color", "colour", "name", "histogram", "gamma**value", "gamma**gain",
                              "intensity", "rescale", "rescale**min", "rescale**max"):
                        k2 = k2.replace("**", "_")
                        # ParameterOverride is 0-indexed
                        param_override.channel_info = (ch_num - 1, {k2: val})  # value has to be a tuple (key, dict)
        except Exception as e:
            log.error(e)

    return param_override
