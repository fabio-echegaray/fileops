from fileops.scripts.config_generate import app
from typer.testing import CliRunner
from unittest import TestCase


class TestConfig(TestCase):
    def __init__(self, *args):
        super().__init__(*args)
        self.runner = CliRunner()

    def test_generate(self):
        # command_name = "generate"
        # args = [command_name, "../summary of CPF data.xlsx", "/media/lab/cache/export/Nikon/Jup-mCh-Sqh-GFP/"]
        args = ["../summary of CPF data.xlsx", "/media/lab/cache/export/Nikon/Jup-mCh-Sqh-GFP/"]

        result = self.runner.invoke(app, args)

        self.assertEqual(result.exit_code, 0)
