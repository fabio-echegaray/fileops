from collections import Counter
from xml.etree import ElementTree as ET

import numpy as np
import pandas as pd
from bioio import BioImage
import bioio_ome_tiff


def _get_metadata(self):
    # biofile_kwargs = {'options': {}, 'original_meta': False, 'memoize': 0, 'dask_tiles': False, 'tile_size': None}
    biofile_kwargs = {}
    with BioImage(self.image_path.as_posix(), reader=bioio_ome_tiff.Reader, **biofile_kwargs) as brdr:
        md_xml = brdr.ome_xml
        md = brdr.ome_metadata

    return md, md_xml


def _get_metadata_from_ome_string(ostr):
    md = ET.fromstring(ostr.encode("utf-8"))

    return md


class NestedDict(dict):
    def __missing__(self, key):
        self[key] = NestedDict()
        return self[key]


def _recurse(d, et, ns):
    etag = et.tag[len(ns) + 2:]

    cnt = Counter([e.tag[len(ns) + 2:] for e in et.getchildren()])
    for child in et:
        # print(child.tag, child.attrib)
        ctag = child.tag[len(ns) + 2:]

        if cnt[ctag] > 1:
            if type(d[etag][ctag]) == NestedDict:
                d[etag][ctag] = []
            d[etag][ctag].append(child.attrib)
        else:
            d[etag][ctag] = _recurse(d[etag][ctag], child, ns)

    d[etag].update(et.attrib)

    return d[etag] if etag != "OME" else d


def ome_info(ome_md, ome_ns) -> pd.Series:
    d = _recurse(NestedDict(), ome_md, ome_ns['ome'])

    if type(d["OME"]["Image"]) == list:
        raise Exception("not cool")

    if type(d["OME"]["Image"]["Pixels"]) == list:
        raise Exception("again, not cool")

    isr_pixels = d["OME"]["Image"]["Pixels"]
    instrument = d["OME"]["Instrument"]
    objective = d["OME"]["Instrument"]["Objective"] if "Objective" in d["OME"]["Instrument"] else None
    obj_id = objective['ID'] if objective else None
    magnification = int(float(objective.get('NominalMagnification'))) if objective else None
    channels = isr_pixels["Channel"]
    if type(channels) == list:
        channels = [c["ID"] for c in channels]
    elif type(channels) == dict or type(channels) == NestedDict:
        channels = [channels["ID"]]

    size_x = int(isr_pixels.get('SizeX'))
    size_y = int(isr_pixels.get('SizeY'))
    size_z = int(isr_pixels.get('SizeZ'))
    size_t = int(isr_pixels.get('SizeT'))
    size_c = int(isr_pixels.get('SizeC'))
    physical_size_x = float(isr_pixels.get('PhysicalSizeX'))
    physical_size_y = float(isr_pixels.get('PhysicalSizeY'))
    physical_size_z = float(isr_pixels.get('PhysicalSizeZ') if 'PhysicalSizeZ' in isr_pixels else 0)
    size_x_unit = isr_pixels.get('PhysicalSizeXUnit')
    size_y_unit = isr_pixels.get('PhysicalSizeYUnit')
    size_z_unit = isr_pixels.get('PhysicalSizeZUnit')

    imgseries_planes = isr_pixels["Plane"]
    timestamps = sorted(
        np.unique([p.get('TheT') for p in imgseries_planes if
                   p.get('TheT') is not None]).astype(np.float64))
    series_info = {
        'image_id':        d['OME']['Image']['ID'],
        'image_name':      d['OME']['Image']['Name'],
        'instrument_id':   instrument['ID'],
        'pixels_id':       d['OME']['Image']['Pixels']['ID'],
        'channels':        channels,
        'n_channels':      size_c,
        'z-stacks':        size_z,  # deprecate this or change it to list of z-stacks
        'n_zstacks':       size_z,
        'frames':          size_t,  # deprecate this or change it to list of frames
        'n_frames':        size_t,
        'delta_t':         float(np.nanmean(np.diff(timestamps))),
        'timestamps':      timestamps,
        'width':           size_x,
        'height':          size_y,
        'data_type':       isr_pixels.get('Type'),
        'objective_id':    obj_id,
        'magnification':   magnification,
        'pixel_size':      (physical_size_x, physical_size_y, physical_size_z),
        'pixel_size_unit': (size_x_unit, size_y_unit, size_z_unit),
        'pix_per_um':      (1 / size_x, 1 / size_y, 1 / size_z),
        'tiff_data':       isr_pixels["TiffData"],
        'planes':          isr_pixels["Plane"],
    }

    out = pd.Series(series_info)
    return out
