from unittest import TestCase

from typer.testing import CliRunner

from fileops.scripts.config import app


class TestConfig(TestCase):
    def __init__(self, *args):
        super().__init__(*args)
        self.runner = CliRunner()

    def test_generate(self):
        """ Test of script that generates config files """
        command_name = "generate"
        args = [command_name, "/media/lab/cache/export/summary of CPF data.fods",
                "/media/lab/cache/export/Nikon/Jup-mCh-Sqh-GFP/"]

        result = self.runner.invoke(app, args)

        self.assertEqual(result.exit_code, 0)

    def test_update(self):
        """ Test of script that update the location of config files based on the master spreadsheet """
        command_name = "update"
        args = [command_name, "/media/lab/cache/export/summary of CPF data.fods", "/media/lab/cache/export/Nikon/"]

        result = self.runner.invoke(app, args)
        print(result.output)

        if result.exit_code != 0:
            print(result.exception)
        self.assertEqual(result.exit_code, 0)

    def test_generate_cfg_content(self):
        """ Test of script that generates a spreadsheet with the content of config files """
        command_name = "generate_config_content"
        args = [command_name, "/media/lab/cache/export/Nikon", "../config_content.xlsx"]

        result = self.runner.invoke(app, args)
        print(result.output)

        if result.exit_code != 0:
            print(result.exception)
        self.assertEqual(result.exit_code, 0)

    def test_edit_cfg_content(self):
        """ Test of script that edit the content of config files based on a spreadsheet """
        command_name = "edit"
        args = [command_name, "../config_content.xlsx"]

        result = self.runner.invoke(app, args)
        print(result.output)

        if result.exit_code != 0:
            print(result.exception)
        self.assertEqual(result.exit_code, 0)


if __name__ == "__main__":
    app()
