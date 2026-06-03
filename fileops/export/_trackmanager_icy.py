import xml.etree.ElementTree as ET

import pandas as pd


def parse_track_xml(xml_file) -> pd.DataFrame:
    """
    Returns track data in Pandas format given a path to an XML file from Icy's plugin Track Manager.
    """
    # Load and parse the XML file
    tree = ET.parse(xml_file)
    root = tree.getroot()

    detections = []

    # Iterate through each trackgroup
    for group in root.findall('trackgroup'):
        group_desc = group.get('description')

        # Iterate through each track in the group
        for track in group.findall('track'):
            track_id = track.get('id')

            # Extract data from each detection point
            for det in track.findall('detection'):
                det_data = {
                    'track_id':   track_id,
                    't':          int(det.get('t')),
                    'x':          int(float(det.get('x'))),
                    'y':          int(float(det.get('y'))),
                    'z':          int(float(det.get('z'))),
                    'track_name': group_desc,
                    'selected':   det.get('selected') == 'true'
                }
                detections.append(det_data)

    return pd.DataFrame(detections)
