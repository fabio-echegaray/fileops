import unittest


class TestConfigGenerate(unittest.TestCase):

    @unittest.skip("Requires hardcoded lab paths")
    def test_generate(self):
        from typer.testing import CliRunner
        from fileops.scripts.config import app
        runner = CliRunner()
        args = ["generate", "/media/lab/cache/export/summary of CPF data.fods",
                "/media/lab/cache/export/Nikon/Jup-mCh-Sqh-GFP/"]
        result = runner.invoke(app, args)
        self.assertEqual(result.exit_code, 0)


class TestConfigUpdate(unittest.TestCase):

    @unittest.skip("Requires hardcoded lab paths")
    def test_update(self):
        from typer.testing import CliRunner
        from fileops.scripts.config import app
        runner = CliRunner()
        args = ["update", "/media/lab/cache/export/summary of CPF data.fods",
                "/media/lab/cache/export/Nikon/",
                "--relative-to", "/media/lab/Data/Microscope"]
        result = runner.invoke(app, args)
        self.assertEqual(result.exit_code, 0)


class TestConfigGenerateContent(unittest.TestCase):

    @unittest.skip("Requires hardcoded lab paths")
    def test_generate_cfg_content(self):
        from typer.testing import CliRunner
        from fileops.scripts.config import app
        runner = CliRunner()
        args = ["generate_config_content", "/media/lab/cache/export/Nikon", "../config_content.xlsx"]
        result = runner.invoke(app, args)
        self.assertEqual(result.exit_code, 0)


class TestConfigEdit(unittest.TestCase):

    @unittest.skip("Requires hardcoded lab paths")
    def test_edit_cfg_content(self):
        from typer.testing import CliRunner
        from fileops.scripts.config import app
        runner = CliRunner()
        args = ["edit", "../config_content.xlsx"]
        result = runner.invoke(app, args)
        self.assertEqual(result.exit_code, 0)


if __name__ == '__main__':
    unittest.main()
