from unittest import TestCase

from typer.testing import CliRunner

from fileops.scripts.config_generate import app as app_generate
from fileops.scripts.config_update import app as app_update
from fileops.scripts.config_edit import app as app_edit


class TestConfig(TestCase):
    def __init__(self, *args):
        super().__init__(*args)
        self.runner = CliRunner()

    def test_generate(self):
        """ Test of script that generates config files """
        args = ["/media/lab/cache/export/summary of CPF data.xlsx", "/media/lab/cache/export/Nikon/Jup-mCh-Sqh-GFP/"]

        result = self.runner.invoke(app_generate, args)

        self.assertEqual(result.exit_code, 0)

    def test_update(self):
        """ Test of script that update the location of config files based on the master spreadsheet """
        args = ["/media/lab/cache/export/summary of CPF data.xlsx", "/media/lab/cache/export/Nikon/"]

        result = self.runner.invoke(app_update, args)
        print(result.output)

        if result.exit_code != 0:
            print(result.exception)
        self.assertEqual(result.exit_code, 0)

    def test_generate_cfg_content(self):
        """ Test of script that generates a spreadsheet with the content of config files """
        command_name = "generate"
        args = [command_name, "/media/lab/cache/export/Nikon", "../config_content.xlsx"]

        result = self.runner.invoke(app_edit, args)
        print(result.output)

        if result.exit_code != 0:
            print(result.exception)
        self.assertEqual(result.exit_code, 0)

    def test_edit_cfg_content(self):
        """ Test of script that edit the content of config files based on a spreadsheet """
        command_name = "edit"
        args = [command_name, "../config_content.xlsx"]

        result = self.runner.invoke(app_edit, args)
        print(result.output)

        if result.exit_code != 0:
            print(result.exception)
        self.assertEqual(result.exit_code, 0)
