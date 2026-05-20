from typer import Typer

from fileops.logger import get_logger
from ._config_update import update
from ._config_edit import generate_config_content, edit_config_content
from ._config_generate import generate

log = get_logger(name='config')
app = Typer()

app.command(name='content_generate')(generate_config_content)
app.command(name='content_edit')(edit_config_content)
app.command(name='generate')(generate)
app.command(name='update')(update)

if __name__ == "__main__":
    app()
