from unittest import TestCase

from typer.testing import CliRunner

from fileops.scripts.config_generate import app as app_generate
from fileops.scripts.config_update import app as app_update


class TestConfig(TestCase):
    def __init__(self, *args):
        super().__init__(*args)
        self.runner = CliRunner()

    def test_generate(self):
        # command_name = "generate"
        # args = [command_name, "../summary of CPF data.xlsx", "/media/lab/cache/export/Nikon/Jup-mCh-Sqh-GFP/"]
        args = ["../summary of CPF data.xlsx", "/media/lab/cache/export/Nikon/Jup-mCh-Sqh-GFP/"]

        result = self.runner.invoke(app_generate, args)

        self.assertEqual(result.exit_code, 0)

    def test_update(self):
        args = ["../summary of CPF data.xlsx", "/media/lab/cache/export/Nikon/"]

        result = self.runner.invoke(app_update, args)

        self.assertEqual(result.exit_code, 0)
