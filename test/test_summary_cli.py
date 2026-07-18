import pytest


@pytest.fixture(scope="module")
def cli_app():
    from typer.testing import CliRunner
    from fileops.scripts.summary import app
    return CliRunner(), app


@pytest.mark.skip(reason="Requires hardcoded lab paths")
class TestSummaryMake:
    def test_make(self, cli_app):
        runner, app = cli_app
        args = ["make", "/media/lab/Data/Fabio/Microscope/Nikon", "../summary.csv", "--guess-date"]
        result = runner.invoke(app, args)
        assert result.exit_code == 0


@pytest.mark.skip(reason="Requires hardcoded lab paths")
class TestSummaryMarkdown:
    def test_generate_markdown(self, cli_app):
        runner, app = cli_app
        args = ["markdown", "/media/lab/cache/export/summary of CPF data.fods"]
        result = runner.invoke(app, args)
        assert result.exit_code == 0


@pytest.mark.skip(reason="Requires hardcoded lab paths")
class TestSummaryMerge:
    def test_merge(self, cli_app):
        runner, app = cli_app
        args = ["merge",
                "/media/lab/cache/export/summary of CPF data.fods",
                "../summary.csv", "../out.csv", "/media/lab/cache/export/"]
        result = runner.invoke(app, args)
        assert result.exit_code == 0
