from unittest import TestCase

from typer.testing import CliRunner

from fileops.scripts.summary import app


class TestSummary(TestCase):
    def __init__(self, *args):
        super().__init__(*args)
        self.runner = CliRunner()

    def test_make(self):
        """ Test of script that creates a master spreadsheet of microscopy files """
        command_name = "make"
        args = [command_name, "/media/lab/Data/Fabio/Microscope/Nikon", "../summary.csv", "--guess-date"]

        result = self.runner.invoke(app, args)
        self.assertEqual(result.exit_code, 0)

    def test_generate_markdown(self):
        """ Test of script that creates a master spreadsheet of microscopy files in markdown format """
        command_name = "markdown"
        path = "/media/lab/cache/export/summary of CPF data.fods"

        args = [command_name, path]

        result = self.runner.invoke(app, args)
        self.assertEqual(result.exit_code, 0)

    def test_merge(self):
        """ Test of script that adds new image files to the master spreadsheet """
        command_name = "merge"
        path_a = "/media/lab/cache/export/summary of CPF data.fods"
        path_b = "../summary.csv"
        path_out = "../out.csv"
        path_cfg = "/media/lab/cache/export/"
        args = [command_name, path_a, path_b, path_out, path_cfg]

        result = self.runner.invoke(app, args)
        self.assertEqual(result.exit_code, 0)


if __name__ == "__main__":
    app()
