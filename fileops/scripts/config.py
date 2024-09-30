from typer import Typer

from fileops.logger import get_logger
from ._config_update import update
from ._config_edit import generate_config_content, edit
from ._config_generate import generate

log = get_logger(name='config')
app = Typer()

app.command()(generate_config_content)
app.command()(generate)
app.command()(edit)
app.command()(update)
