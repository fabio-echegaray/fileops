import pytest


@pytest.fixture(scope="module")
def cli_app():
    from typer.testing import CliRunner
    from fileops.scripts.config import app
    return CliRunner(), app


@pytest.mark.skip(reason="Requires hardcoded lab paths")
class TestConfigGenerate:
    def test_generate(self, cli_app):
        runner, app = cli_app
        args = ["generate", "/media/lab/cache/export/summary of CPF data.fods",
                "/media/lab/cache/export/Nikon/Jup-mCh-Sqh-GFP/"]
        result = runner.invoke(app, args)
        assert result.exit_code == 0


@pytest.mark.skip(reason="Requires hardcoded lab paths")
class TestConfigUpdate:
    def test_update(self, cli_app):
        runner, app = cli_app
        args = ["update", "/media/lab/cache/export/summary of CPF data.fods",
                "/media/lab/cache/export/Nikon/",
                "--relative-to", "/media/lab/Data/Microscope"]
        result = runner.invoke(app, args)
        assert result.exit_code == 0


@pytest.mark.skip(reason="Requires hardcoded lab paths")
class TestConfigGenerateContent:
    def test_generate_cfg_content(self, cli_app):
        runner, app = cli_app
        args = ["generate_config_content", "/media/lab/cache/export/Nikon", "../config_content.xlsx"]
        result = runner.invoke(app, args)
        assert result.exit_code == 0


@pytest.mark.skip(reason="Requires hardcoded lab paths")
class TestConfigEdit:
    def test_edit_cfg_content(self, cli_app):
        runner, app = cli_app
        args = ["edit", "../config_content.xlsx"]
        result = runner.invoke(app, args)
        assert result.exit_code == 0
