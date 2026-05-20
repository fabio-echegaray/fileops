import pandas as pd
from pytrackmate import trackmate_peak_import


def parse_track_xml(xml_file) -> pd.DataFrame:
    """
    Returns track data in Pandas format given a path to an XML file from Trackmate.
    """
    trk = trackmate_peak_import(xml_file, get_tracks=True)
    # trk.rename(columns={'x': 'x_um', 'y': 'y_um'}, inplace=True)
    trk["x"] = trk["x"].astype(int)
    trk["y"] = trk["y"].astype(int)
    trk["t"] = trk["t"].astype(int)
    trk["track_id"] = trk["label"]
    trk["track_name"] = trk["label"].apply(lambda lbl: f"track_{int(lbl):04d}")

    return trk
