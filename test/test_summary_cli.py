import unittest


class TestSummaryMake(unittest.TestCase):

    @unittest.skip("Requires hardcoded lab paths")
    def test_make(self):
        from typer.testing import CliRunner
        from fileops.scripts.summary import app
        runner = CliRunner()
        args = ["make", "/media/lab/Data/Fabio/Microscope/Nikon", "../summary.csv", "--guess-date"]
        result = runner.invoke(app, args)
        self.assertEqual(result.exit_code, 0)


class TestSummaryMarkdown(unittest.TestCase):

    @unittest.skip("Requires hardcoded lab paths")
    def test_generate_markdown(self):
        from typer.testing import CliRunner
        from fileops.scripts.summary import app
        runner = CliRunner()
        args = ["markdown", "/media/lab/cache/export/summary of CPF data.fods"]
        result = runner.invoke(app, args)
        self.assertEqual(result.exit_code, 0)


class TestSummaryMerge(unittest.TestCase):

    @unittest.skip("Requires hardcoded lab paths")
    def test_merge(self):
        from typer.testing import CliRunner
        from fileops.scripts.summary import app
        runner = CliRunner()
        args = ["merge",
                "/media/lab/cache/export/summary of CPF data.fods",
                "../summary.csv", "../out.csv", "/media/lab/cache/export/"]
        result = runner.invoke(app, args)
        self.assertEqual(result.exit_code, 0)


if __name__ == '__main__':
    unittest.main()
