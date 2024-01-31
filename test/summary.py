from fileops.scripts.summary import app
from typer.testing import CliRunner
from unittest import TestCase


class TestSummary(TestCase):
    def __init__(self, *args):
        super().__init__(*args)
        self.runner = CliRunner()

    def test_make(self):
        command_name = "make"
        args = [command_name, "/media/lab/Data/Fabio/Microscope/Nikon"]

        result = self.runner.invoke(app, args)
        self.assertEqual(result.exit_code, 0)

    def test_merge(self):
        command_name = "merge"
        args = [command_name, "../summary of CPF data.xlsx", "../summary.xlsx", "../out.csv"]

        result = self.runner.invoke(app, args)
        self.assertEqual(result.exit_code, 0)
