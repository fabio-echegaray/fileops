import fnmatch
import os
from pathlib import Path
from typing import Union, List


def ensure_dir(dir_path: Union[str, Path]):
    is_path = type(dir_path) == Path
    adir_path = os.path.abspath(dir_path)
    if not os.path.exists(adir_path):
        os.makedirs(adir_path, exist_ok=True)
    return Path(dir_path) if is_path else dir_path


def find(pattern, path) -> List[Path]:
    result = []
    for root, dirs, files in os.walk(path):
        for name in files:
            if fnmatch.fnmatch(name, pattern):
                result.append(Path(root) / name)
    return result
