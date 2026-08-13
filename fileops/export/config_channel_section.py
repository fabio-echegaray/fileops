import configparser
from pathlib import Path

import numpy as np

from fileops.export._param_override import ParameterOverride
from fileops.logger import get_logger

log = get_logger(name='export')

# keys that describe a channel itself (not the image as a whole). These are the
# only keys from a configparser [DEFAULT] section that are allowed to remain on
# a [CHANNEL-N] entry, because the renderers/channel_configuration consume them.
_CHANNEL_ATTRIBUTE_KEYS = {
    "name", "color", "colour", "histogram", "intensity",
    "rescale", "rescale_min", "rescale_max",
    "gamma_value", "gamma_gain", "reference_frame",
}


# ----------------------------------------------------------------------------------------------------------------------
#  routines that override parameters in channel sections of the config file
# ----------------------------------------------------------------------------------------------------------------------
def update_overrides_from_channel_sections(param_override: ParameterOverride, cfg_path,
                                           defaults_file: Path | None = None) -> ParameterOverride:
    cfg = configparser.ConfigParser()
    if defaults_file is not None:
        cfg.read(defaults_file)
    cfg.read(cfg_path)

    ch_sections = [s for s in cfg.sections() if "CHANNEL" in s]
    if len(ch_sections) == 0:
        log.info(f"No CHANNEL header in file {cfg_path}.")
        # generate default channel configuration
        for ch_num in param_override.channels:
            param_override.channel_info = (ch_num, dict(name=f"ch-{ch_num:02d}"))  # value has to be a tuple (key, dict)

        return param_override

    # configparser injects every key from the project-level [DEFAULT] section into
    # every section. For channel sections we must keep only the keys that are
    # actually channel attributes (name, color, rescale, gamma, ...) and drop the
    # image-level processing flags (photobleach_correction, histogram_matching,
    # rescale at the DATA level, etc.). Keeping `rescale`/`rescale_min`/`rescale_max`
    # here is essential: the image-level RescaleProcessor (see rescale_proc.py)
    # reads the per-channel `rescale` flag from channel_configuration, so stripping
    # it makes channels render un-rescaled (flat/dim).
    default_keys = set(cfg.defaults())
    for ch_sec in ch_sections:
        ch_num = int(ch_sec.split("-")[1])
        section_data = cfg[ch_sec]
        section_data = {
            k: v for k, v in section_data.items()
            if k in _CHANNEL_ATTRIBUTE_KEYS or k not in default_keys
        }
        # ch_key at this level is 1-indexed, but for at the level of ParameterOverride it's 0-indexed
        param_override.channel_info = (ch_num - 1, section_data)  # value has to be a tuple (key, dict)

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


def channel_configuration(channel_render_parameters):
    ch_config = dict()
    for cix, ch_cfg in channel_render_parameters.items():
        ch_config[ch_cfg['name']] = {
            'id':        cix,
            'color':     ch_cfg['color'][1:] if (
                    isinstance(ch_cfg['color'], tuple) and
                    len(ch_cfg['color']) > 3
            ) else ch_cfg['color'],
            'intensity': float(ch_cfg['intensity']) if 'intensity' in ch_cfg else 1.0
        }
        if np.any(['rescale' in k for k in ch_cfg.keys()]):
            ch_config[ch_cfg['name']].update({
                'rescale': ch_cfg['rescale'].lower() in ['true', 'yes']
                           if 'rescale' in ch_cfg else True
            })
            if 'rescale_min' in ch_cfg:
                ch_config[ch_cfg['name']].update({'rescale_min': float(ch_cfg['rescale_min'])})
            if 'rescale_max' in ch_cfg:
                ch_config[ch_cfg['name']].update({'rescale_max': float(ch_cfg['rescale_max'])})

        elif np.any(['gamma' in k for k in ch_cfg.keys()]):
            ch_config[ch_cfg['name']].update({
                'gamma_value': float(ch_cfg['gamma_value']) if 'gamma_value' in ch_cfg else 1.0,
                'gamma_gain':  float(ch_cfg['gamma_gain']) if 'gamma_gain' in ch_cfg else 1.0
            })
    return ch_config
