import os
from pathlib import Path
from typing import Union


def ensure_dir(dir_path: Union[str, Path]):
    dir_path = os.path.abspath(dir_path)
    if not os.path.exists(dir_path):
        os.makedirs(dir_path, exist_ok=True)
    return dir_path
