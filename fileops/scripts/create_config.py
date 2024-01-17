import os
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from fileops.export.config import create_cfg_file
from fileops.logger import get_logger
from fileops.pathutils import ensure_dir

log = get_logger(name='create_config')

if __name__ == '__main__':
    rename_folder = False
    exp_path = Path("/media/lab/Data/Fabio/export/Nikon/Jup-mCh-Sqh-GFP/")

    df = pd.read_excel("summary of CPF data.xlsx")

    for ix, r in df.iterrows():
        if r["cfg_path"] == "-":
            continue
        elif ((type(r["cfg_path"]) == float and np.isnan(r["cfg_path"])) or
              (type(r["cfg_path"]) == str and len(r["cfg_path"]) == 0)):
            if ((type(r["cfg_folder"]) == float and np.isnan(r["cfg_folder"])) or
                    (type(r["cfg_folder"]) == str and len(r["cfg_folder"]) == 0)):
                continue
            else:
                cfg_path = ensure_dir(exp_path / r["cfg_folder"]) / "export_definition.cfg"
                img_path = Path(r["folder"]) / r["filename"]
                cr_datetime = datetime.fromtimestamp(os.path.getmtime(img_path))

                create_cfg_file(path=cfg_path,
                                contents={
                                    "DATA":  {
                                        "image":   img_path.as_posix(),
                                        "series":  0,  # TODO: change
                                        "channel": [0, 1],  # TODO: change
                                        "frame":   "all"
                                    },
                                    "MOVIE": {
                                        "title":       "Lorem Ipsum",
                                        "description": "The story behind Lorem Ipsum",
                                        "fps":         10,
                                        "layout":      "twoch",
                                        "zstack":      "all-max",
                                        "filename":    f"{cr_datetime.strftime('%Y%m%d')}-"
                                                       f"{'-'.join(r['cfg_folder'].split('-')[1:])}"
                                    }
                                })
        else:
            cfg_path = Path(r["cfg_path"])

            if not cfg_path.exists():
                log.warning("Configuration path did not exist. "
                            "This parameter is usually written down by an automated script, "
                            "check your source sheet and folder structure.\r\n"
                            f"{cfg_path.as_posix()}")
