import os
from pathlib import Path
from typing import Union


def ensure_dir(dir_path: Union[str, Path]):
    is_path = type(dir_path) == Path
    adir_path = os.path.abspath(dir_path)
    if not os.path.exists(adir_path):
        os.makedirs(adir_path, exist_ok=True)
    return Path(dir_path) if is_path else dir_path
