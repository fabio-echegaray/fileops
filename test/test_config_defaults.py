import configparser
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from fileops.export.config import read_config
from fileops.export.config_data_section import read_data_section


class _StubImage:
    """Minimal stand-in for an ImageFile opened by read_data_section."""
    frames = list(range(5))
    channels = [0, 1]
    zstacks = [0, 1]
    series = 0

    def add_processor(self, *args, **kwargs):
        pass


def _make_files(tmpdir, cfg_text, defaults_text=None):
    img_path = tmpdir / "data.tif"
    img_path.write_bytes(b"stub")

    cfg_path = tmpdir / "movie.cfg"
    cfg_path.write_text(cfg_text)

    defaults_path = None
    if defaults_text is not None:
        defaults_path = tmpdir / "defaults.cfg"
        defaults_path.write_text(defaults_text)

    return cfg_path, defaults_path


CFG_TEXT = """
[DATA]
image = data.tif

[MOVIE-1]
filename = my_movie
layout = twoch

[CHANNEL-1]
name = cell-specific
"""

DEFAULTS_TEXT = """
[DEFAULT]
fps = 15
layout = threech
rescale = yes
channel_1_color = magenta

[CHANNEL-1]
name = gfp
"""


class TestReadDataSectionDefaults(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    @patch("fileops.export.config_data_section.load_image_file", return_value=_StubImage())
    def test_defaults_merge_and_section_priority(self, mock_load):
        cfg_path, defaults_path = _make_files(
            self.tmp,
            CFG_TEXT,
            "[DEFAULT]\nfps = 15\nlayout = threech\nrescale = yes\n",
        )

        cfg, img_file, param_override, roi = read_data_section(cfg_path, defaults_file=defaults_path)

        # value only defined in the defaults [DEFAULT] section is inherited
        self.assertEqual(cfg["MOVIE-1"]["fps"], "15")
        # value defined in both: the configuration section wins
        self.assertEqual(cfg["MOVIE-1"]["layout"], "twoch")
        # cfg sections not in the defaults file keep their own values
        self.assertEqual(cfg["DATA"]["image"], "data.tif")
        self.assertEqual(param_override.channels, [0, 1])

    @patch("fileops.export.config_data_section.load_image_file", return_value=_StubImage())
    def test_defaults_channel_section_applies(self, mock_load):
        cfg_path, defaults_path = _make_files(
            self.tmp,
            "[DATA]\nimage = data.tif\n",
            "[CHANNEL-1]\nname = gfp\ncolor = magenta\n",
        )

        cfg, img_file, param_override, roi = read_data_section(cfg_path, defaults_file=defaults_path)

        # default channel configuration from the defaults file is used
        self.assertEqual(param_override.channel_info[0]["name"], "gfp")

    @patch("fileops.export.config_data_section.load_image_file", return_value=_StubImage())
    def test_cfg_channel_section_overrides_defaults(self, mock_load):
        cfg_path, defaults_path = _make_files(
            self.tmp,
            CFG_TEXT,
            DEFAULTS_TEXT,
        )

        cfg, img_file, param_override, roi = read_data_section(cfg_path, defaults_file=defaults_path)

        # channel config defined in the configuration file wins over the defaults file
        self.assertEqual(param_override.channel_info[0]["name"], "cell-specific")

    @patch("fileops.export.config_data_section.load_image_file", return_value=_StubImage())
    def test_default_channel_attributes_are_inherited_and_inert_flags_stripped(self, mock_load):
        cfg_path, defaults_path = _make_files(
            self.tmp,
            "[DATA]\nimage = data.tif\n\n[CHANNEL-1]\nname = cell-specific\n",
            "[DEFAULT]\nrescale = yes\nphotobleach_correction = yes\nhistogram_matching = yes\n",
        )

        cfg, img_file, param_override, roi = read_data_section(cfg_path, defaults_file=defaults_path)

        channel_0 = param_override.channel_info[0]
        # the config-file name wins over any defaults
        self.assertEqual(channel_0["name"], "cell-specific")
        # channel-relevant defaults (rescale) must still be inherited, because the
        # image-level RescaleProcessor reads the per-channel `rescale` flag
        self.assertIn("rescale", channel_0)
        self.assertEqual(channel_0["rescale"], "yes")
        # image-level processing flags must NOT leak into channel definitions
        self.assertNotIn("photobleach_correction", channel_0)
        self.assertNotIn("histogram_matching", channel_0)

    @patch("fileops.export.config_data_section.load_image_file", return_value=_StubImage())
    def test_no_defaults_file_unchanged(self, mock_load):
        cfg_path, _ = _make_files(self.tmp, CFG_TEXT)

        cfg, img_file, param_override, roi = read_data_section(cfg_path)

        self.assertEqual(cfg["MOVIE-1"]["layout"], "twoch")
        self.assertNotIn("fps", cfg["MOVIE-1"])


class TestReadConfigDefaults(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    @patch("fileops.export.config_data_section.load_image_file", return_value=_StubImage())
    @patch("fileops.export.config.read_config_projections", return_value=[])
    @patch("fileops.export.config.read_config_tracks", return_value=[])
    @patch("fileops.export.config.read_config_copyright", return_value=None)
    @patch("fileops.config_type_plugins", [])
    @patch("fileops.header_reader_plugins", [])
    def test_read_config_merges_defaults(self, *_mocks):
        cfg_path, defaults_path = _make_files(
            self.tmp,
            CFG_TEXT,
            "[DEFAULT]\nfps = 15\nlayout = threech\n",
        )

        exp = read_config(cfg_path, defaults_file=defaults_path)

        self.assertEqual(exp.config_file["MOVIE-1"]["fps"], "15")
        self.assertEqual(exp.config_file["MOVIE-1"]["layout"], "twoch")


class TestDefaultsFileParsing(unittest.TestCase):
    """The defaults file must be valid configparser syntax with a [DEFAULT] section."""

    def test_defaults_file_is_parseable(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            df = Path(tmpdir) / "defaults.cfg"
            df.write_text("[DEFAULT]\nfps = 15\nchannel_1_color = (1, 0, 1, 0)\n")
            cfg = configparser.ConfigParser()
            cfg.read(df)
            self.assertEqual(cfg["DEFAULT"]["fps"], "15")
            self.assertEqual(cfg["DEFAULT"]["channel_1_color"], "(1, 0, 1, 0)")


class TestChannelOverridesFromDefaults(unittest.TestCase):
    """channel_* keys in the defaults [DEFAULT] section apply to every section."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def test_channel_color_and_gamma_from_defaults(self):
        from fileops.export._param_override import ParameterOverride
        from fileops.export.config_channel_section import update_channel_config_with_section_overrides
        from fileops.plugins import HeaderReaderPlugin

        cfg_path, defaults_path = _make_files(
            self.tmp,
            "[DATA]\nimage = data.tif\n\n[MOVIE-1]\nfilename = my_movie\n",
            "[DEFAULT]\nchannel_1_color = magenta\nchannel_1_gamma_value = 1.5\n",
        )

        plugin = HeaderReaderPlugin(cfg_path, defaults_file=defaults_path)
        povrr = ParameterOverride(_StubImage())
        povrr = update_channel_config_with_section_overrides(povrr, plugin._cfg["MOVIE-1"])

        self.assertEqual(povrr.channel_info[0]["color"], "magenta")
        self.assertEqual(povrr.channel_info[0]["gamma_value"], 1.5)


if __name__ == '__main__':
    unittest.main()
