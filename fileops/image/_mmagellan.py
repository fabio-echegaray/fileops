import pathlib

import numpy as np


def folder_is_micromagellan(path: str) -> bool:
    # get to a path level that contains sub-folders
    p = pathlib.Path(path)
    keep_exploring = True
    while keep_exploring:
        folders = [x for x in p.iterdir() if x.is_dir()]
        keep_exploring = p.parent != p.root and not folders
        p = p.parent
    key_full_res = [f for f in folders if 'Full resolution' in f.name]
    if key_full_res:
        folders.pop(folders.index(key_full_res[0]))
        key_folders = [np.any([f'Downsampled_x{2 ** i:d}' in f.name for i in range(1, 12)]) for f in folders]
        return np.all(key_folders)
    else:
        return False
