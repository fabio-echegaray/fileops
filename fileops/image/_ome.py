from typing import Dict, Iterable

import numpy as np
from ome_types import OME


def ome_info(md_ome: OME) -> Iterable[Dict]:
    if md_ome is None:
        raise ValueError
    for im in md_ome.images:
        channels = im.pixels.channels

        earliest_aquisition = min(im.acquisition_date for im in md_ome.images)
        if earliest_aquisition is not None:
            earliest_aquisition = earliest_aquisition.strftime("%a %b/%d/%Y, %H:%M:%S")
        size_x = int(im.pixels.size_x)
        size_y = int(im.pixels.size_y)
        size_z = int(im.pixels.size_z)
        size_t = int(im.pixels.size_t)
        size_c = int(im.pixels.size_c)
        physical_size_x = float(im.pixels.physical_size_x)
        physical_size_y = float(im.pixels.physical_size_y)
        physical_size_z = float(im.pixels.physical_size_z) if im.pixels.physical_size_z is not None else np.nan
        size_x_unit = im.pixels.physical_size_x_unit
        size_y_unit = im.pixels.physical_size_y_unit
        size_z_unit = im.pixels.physical_size_z_unit
        n_frames = size_t
        n_channels = size_c
        n_zstacks = size_z
        ts_diff = float(im.pixels.time_increment) if im.pixels.time_increment is not None else np.nan

        assert size_x_unit == size_y_unit == size_z_unit
        if len(im.instrument_ref.ref.objectives) > 0:
            objective = im.instrument_ref.ref.objectives[0]
            objective_id = f"{int(objective.nominal_magnification)}X/{objective.lens_na}" if (
                    objective.nominal_magnification is not None and objective.lens_na is not None) else "N/A"
            mag = int(objective.nominal_magnification) if objective.nominal_magnification is not None else np.nan
        else:
            objective_id = "N/A"
            mag = np.nan
        yield {
            'image_id':         im.id,
            'image_name':       im.name,
            'instrument_id':    im.instrument_ref.id,
            'pixels_id':        im.pixels.id,
            'channels':         n_channels,
            'z-stacks':         n_zstacks,
            'frames':           n_frames,
            'delta_t':          ts_diff,
            'width':            size_x,
            'height':           size_y,
            'data_type':        im.pixels.type.numpy_dtype,
            'objective_id':     objective_id,
            'magnification':    mag,
            'pixel_size':       (physical_size_x, physical_size_y),
            'pix_per_um':       (1 / physical_size_x, 1 / physical_size_y),
            'pixel_size_unit':  size_x_unit.value,
            'z_step_size':      physical_size_z,
            'z_step_size_unit': size_z_unit.value,
            'channel_names':    [c.name for c in channels],
            'acquisition':      earliest_aquisition
        }
