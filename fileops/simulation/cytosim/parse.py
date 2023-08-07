import re

import pandas as pd


def parse_cytosim_output(path) -> pd.DataFrame:
    timepoints = list()
    frame = time = clusters = c_freq = None
    with open(path) as f:
        while True:
            txt = f.readline()
            if not txt:
                break
            if txt[:7] == "% frame":
                frame = int(txt[7:])
            elif txt[:6] == "% time":
                time = float(txt[6:])
            elif txt[:10] == "%  cluster":
                txt = f.readline()
                clusters = int(re.search(r'^[\s\t]+(\d+) clusters', txt).groups()[0])
                c_freq = list()
                for i in range(clusters):
                    txt = f.readline()
                    c_freq.append(int(re.search(r'^\s+(\d+)\s+(\d+) :', txt).groups()[1]))
            elif txt[:5] == "% end":
                timepoints.append({
                    'frame':     frame,
                    'time':      time,
                    'clusters':  clusters,
                    'frequency': c_freq,
                })
                frame = time = clusters = None
    return pd.DataFrame(timepoints)
