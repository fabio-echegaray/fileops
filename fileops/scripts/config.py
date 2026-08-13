from typer import Typer

from fileops.logger import get_logger
from ._config_edit import generate_config_content_cli, edit_config_content
from ._config_generate import generate_cli
from ._config_update import update_cli

log = get_logger(name='config')
app = Typer()

app.command(name='content_generate')(generate_config_content_cli)
app.command(name='content_edit')(edit_config_content)
app.command(name='generate')(generate_cli)
app.command(name='update')(update_cli)

if __name__ == "__main__":
    app()
