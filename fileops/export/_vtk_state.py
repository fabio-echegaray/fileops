from pathlib import Path
from typing import Dict

from jinja2 import Environment, FileSystemLoader
import fileops


def save_vtk_python_state(save_path, general_info: Dict, channel_info: Dict):
    """ write a paraview state file (in Python format) to be loaded from file->Load State """
    fileops_path = Path(fileops.__file__).parent
    environment = Environment(loader=FileSystemLoader(fileops_path / "export"))
    template = environment.get_template("vtk_state.tmpl")

    with open(save_path, "w") as f:
        f.write(template.render(info=general_info, channels=channel_info))
