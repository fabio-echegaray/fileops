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
from fileops.image.imagemeta import MetadataImage
from fileops.image.ops import rescale
from fileops.image.ops.rescale_proc import RescaleProcessor, configure_rescale_processor


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


@pytest.mark.parametrize("body", [
    "channel_1_gamma_value = 4.0\nchannel_1_gamma_gain = 2.0\n",
    "channel_1_gamma_gain = 2.0\nchannel_1_gamma_value = 4.0\n",
])
def test_gamma_value_and_gain_together_are_both_kept(body):
    """A section that sets both `gamma_value` and `gamma_gain` must keep both values.

    Scenario: `[MOVIE]` sets `channel_1_gamma_value = 4.0` and `channel_1_gamma_gain = 2.0`, in either order.
    Symptom: the channel renders with gamma_value 1.0 (only the gain survives); no warning is logged.
    Cause: each `channel_N_*` key is applied as its own item, and the setter (fix for #54) defaulted the
    missing half of the pair to 1.0 on every item, so the `gamma_gain` item reset the stored gamma_value.
    Guards: both values survive regardless of key order.
    """
    sec = _section(f"[MOVIE]\n{body}")
    po = update_channel_config_with_section_overrides(ParameterOverride(_StubImage()), sec)
    assert po.channel_info[0]["gamma_value"] == 4.0
    assert po.channel_info[0]["gamma_gain"] == 2.0


def test_lone_gamma_gain_does_not_reset_gamma_value():
    """A `gamma_gain` added where a `gamma_value` is already set must not reset the value.

    Scenario: defaults.cfg sets `channel_1_gamma_value = 4.0`; the cfg adds `channel_1_gamma_gain = 2.0`,
    so the same channel receives the two keys from two separate sections (merged files).
    Symptom: the merged channel renders with gamma_value 1.0.
    Cause: the per-item gamma defaulting overwrote the value stored by the earlier section (#59).
    Guards: adding a gain leaves an already-set value untouched.
    """
    po = update_channel_config_with_section_overrides(
        ParameterOverride(_StubImage()), _section("[MOVIE]\nchannel_1_gamma_value = 4.0\n"))
    po = update_channel_config_with_section_overrides(
        po, _section("[PANEL]\nchannel_1_gamma_gain = 2.0\n"))
    assert po.channel_info[0]["gamma_value"] == 4.0
    assert po.channel_info[0]["gamma_gain"] == 2.0


def test_section_gamma_override_reaches_rescale_processor():
    """A [MOVIE]/[PANEL] `channel_N_gamma_*` override must change the pixels the processor produces.

    Scenario: the [DATA] section builds a RescaleProcessor from the [CHANNEL-NN] sections once;
    later a [MOVIE]/[PANEL] section adds `channel_1_gamma_value = 2.0`.
    Symptom: the override shows up in the section's channel_render_parameters, but the rendered
    pixels are identical to a render without it.
    Cause: RescaleProcessor snapshots its channel configuration at [DATA] read time
    (config_data_section.py builds it from param_override.channel_info) and is shared by all
    sections, so per-section overrides never reach the pixels.
    Guards: reconfiguring the shared processor with the section's channel_render_parameters
    (as the renderers do at render time) makes the override take effect.
    """
    # what [DATA] reads: a RescaleProcessor built from the [CHANNEL-NN] sections
    data_level_po = ParameterOverride(_StubImage())
    data_level_po.channel_info = (0, dict(name="ch-01"))
    data_level_po.channel_info = (1, dict(name="ch-02"))

    img = np.linspace(0, 1, 16, dtype=np.uint16).reshape(4, 4)
    mdi = MetadataImage(reader="test", image=img, pix_per_um=1, um_per_pix=1,
                        time_interval=1, frame=0, channel=0, z=0,
                        width=4, height=4, timestamp=0, intensity_range=(0, 1))

    # [DATA]-level processor (as attached by config_data_section.py): no gamma anywhere
    proc = RescaleProcessor(data_level_po.channel_info)
    baseline = proc.process(mdi).image
    assert baseline.shape == img.shape

    # the section's merged channel_render_parameters carry the override
    sec = _section("[MOVIE]\nchannel_1_gamma_value = 2.0\n")
    sec_po = update_channel_config_with_section_overrides(ParameterOverride(_StubImage()), sec)
    assert sec_po.channel_info[0]["gamma_value"] == 2.0

    # render-time reconfiguration makes the override reach the processor
    class _StubImageFile:
        processing_deque = []
        n_frames = 2
        n_channels = 2
        n_zstacks = 2
        add_processor = lambda self, p: self.processing_deque.append(p)

    imf = _StubImageFile()
    imf.processing_deque = []
    imf.add_processor(proc)
    configure_rescale_processor(imf, sec_po.channel_info)

    assert not np.allclose(proc.process(mdi).image, img)


def test_configure_rescale_processor_creates_missing_processor():
    """A section-only gamma/rescale override must create a RescaleProcessor when [DATA] did not.

    Scenario: [DATA] has no `rescale = yes` and no channel rescale_min/max, so config_data_section.py
    never builds a RescaleProcessor; a [PANEL] section still sets `channel_1_gamma_value`.
    Symptom: the override is present in channel_render_parameters but the pixels are untouched.
    Guards: configure_rescale_processor() adds the missing processor so the section's overrides apply,
    and leaves the shared image file alone when the section carries no gamma/rescale settings.
    """
    sec = _section("[PANEL]\nchannel_1_gamma_value = 1.5\n")
    sec_po = update_channel_config_with_section_overrides(ParameterOverride(_StubImage()), sec)

    class _StubImageFile:
        def __init__(self):
            self.processing_deque = []

        def add_processor(self, p):
            self.processing_deque.append(p)

    imf = _StubImageFile()
    configure_rescale_processor(imf, sec_po.channel_info)
    assert len(imf.processing_deque) == 1
    assert isinstance(imf.processing_deque[0], RescaleProcessor)

    # a section without any gamma/rescale setting must not force a processor in
    clean_po = ParameterOverride(_StubImage())
    clean_po.channel_info = (0, dict(name="ch-01"))
    imf2 = _StubImageFile()
    configure_rescale_processor(imf2, clean_po.channel_info)
    assert len(imf2.processing_deque) == 0
