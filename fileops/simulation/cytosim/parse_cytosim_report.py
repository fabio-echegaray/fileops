import os
from pathlib import Path

import pandas as pd

from cytosim.parse import parse_cytosim_output

if __name__ == "__main__":
    data = pd.DataFrame()
    for root, directories, files in os.walk("cytosim/actomyosin_sweep/treadmill/"):
        for file in files:
            if file == 'fcluster.csv':
                fpath = Path(root).joinpath(file)
                print(f"Processing {fpath}")
                df = parse_cytosim_output(fpath)
                df['run'] = fpath.parent.name

                data = data.append(df, ignore_index=True)

    data.to_csv('cytosim.csv')
