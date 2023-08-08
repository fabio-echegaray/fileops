from typing import Dict

from jinja2 import Environment, FileSystemLoader


def save_vtk_python_state(save_path, channel_info: Dict):
    environment = Environment(loader=FileSystemLoader("export/"))
    template = environment.get_template("vtk_state.tmpl")

    with open(save_path, "w") as f:
        f.write(template.render(channels=channel_info))
