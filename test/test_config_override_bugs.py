"""Tests for how parameters from defaults files and from [MOVIE]/[PANEL] sections are resolved into overrides.

Each test has two jobs:
  * expose a bug that exists today: the test asserts the *intended* behaviour, so it FAILS until the bug is fixed;
  * guard against regression: once the bug is fixed, the same test keeps the behaviour from breaking again.
Every docstring states the scenario, the symptom a user sees, and the cause in the code.
"""
import configparser

import numpy as np
import pytest

from fileops.export._param_override import ParameterOverride
from fileops.export.config_channel_section import update_channel_config_with_section_overrides
from fileops.export.config_sections import process_overrides_of_section
from fileops.image.ops import rescale


class _StubImage:
    frames = list(range(696))
    channels = [0, 1]
    zstacks = list(range(25))
    n_frames = 696
    n_channels = 2
    n_zstacks = 25


def _section(text: str):
    cp = configparser.ConfigParser()
    cp.read_string(text)
    return cp[cp.sections()[0]]


def test_frame_and_frames_keys_together_select_cfg_frames():
    """A cfg that selects frames must win over the `frame = all` of a defaults file, whatever the key spelling.

    Scenario: defaults.cfg has `[DATA] frame = all`; the cfg being rendered has `[DATA] frames = [10, 50, 109, 133]`.
    The two files are merged into one [DATA] section that holds both a `frame` and a `frames` key.
    Symptom: the panel draws all 696 frames (about 2000 subplots, ~90 s) instead of the 4 requested, with no warning.
    Cause: process_overrides_of_section() (config_sections.py) applies a frame setting only when exactly one key
    starts with "frame"; with two it silently applies none, so the default (all frames) stands.
    Guards: frame selection stays effective when `frame`/`frames` are spelled differently across defaults and cfg.
    """
    sec = _section("[DATA]\nframe = all\nframes = [10, 50, 109, 133]\n")
    po = process_overrides_of_section(sec, ParameterOverride(_StubImage()), _StubImage())
    assert po.frames == [10, 50, 109, 133]


@pytest.mark.parametrize("key,value", [("font_size", "9"), ("font_name", "Arial"),
                                       ("font_color", "white"), ("font_weight", "bold")])
def test_channel_font_override_reaches_channel_info(key, value):
    """A `channel_N_font_*` key in a section must show up in that channel's parameters.

    Scenario: `[MOVIE]` or `[PANEL]` contains e.g. `channel_1_font_size = 9` (also font_name/font_color/font_weight).
    Symptom: the font setting is ignored; no error or warning is logged.
    Cause: update_channel_config_with_section_overrides() (config_channel_section.py) rewrites the key to
    `font**size` for splitting, but then checks it against an allow-list that spells it `font_size`, so the
    check never matches and the key is skipped.
    Guards: every documented channel font attribute keeps reaching channel_info (0-indexed channel 1 -> key 0).
    """
    sec = _section(f"[MOVIE]\nchannel_1_{key} = {value}\n")
    po = update_channel_config_with_section_overrides(ParameterOverride(_StubImage()), sec)
    assert po.channel_info.get(0, {}).get(key) == value


def test_gamma_value_alone_defaults_gain_and_changes_image():
    """Giving only `gamma_value` must apply a gamma correction, with the gain defaulting to 1.0.

    Scenario: a section has `channel_1_gamma_value = 2.0` and no `gamma_gain`.
    Symptom: the channel is rendered with no gamma correction at all; no warning is logged.
    Cause: the override keeps only `gamma_value`, and rescale() (image/ops/_image_rescale.py) applies gamma only
    when BOTH `gamma_value` and `gamma_gain` are present; nothing supplies the missing gain.
    Guards: the gain keeps defaulting to 1.0, and the resulting settings really change the pixels.
    """
    sec = _section("[MOVIE]\nchannel_1_gamma_value = 2.0\n")
    po = update_channel_config_with_section_overrides(ParameterOverride(_StubImage()), sec)
    settings = po.channel_info[0]
    assert settings["gamma_value"] == 2.0
    assert settings.get("gamma_gain") == 1.0  # the gain should default

    img = np.linspace(0, 1, 16, dtype=np.float64).reshape(4, 4)
    assert not np.allclose(rescale(img, settings), img)
