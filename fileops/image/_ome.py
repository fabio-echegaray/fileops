from datetime import timedelta
from typing import Dict, Iterable

import numpy as np
import pandas as pd
from ome_types import OME
from ome_types.model import Image
from ome_types.model.simple_types import UnitsTime

# Define the explicit mapping of time units
OME_TO_PANDAS_UNITS = {
    UnitsTime.DAY:         "day",
    UnitsTime.HOUR:        "hour",
    UnitsTime.MINUTE:      "minute",
    UnitsTime.SECOND:      "second",
    UnitsTime.MILLISECOND: "ms",
    UnitsTime.MICROSECOND: "us",
    UnitsTime.NANOSECOND:  "ns",
}


def to_pandas_unit(ome_unit: UnitsTime) -> str:
    """Converts an ome_types UnitsTime enum to a pandas UnitChoices string."""
    if ome_unit in OME_TO_PANDAS_UNITS:
        return OME_TO_PANDAS_UNITS[ome_unit]

    # Fallback/Truncation for extreme SI units not natively backed by pandas Timedelta
    # e.g., picosecond, femtosecond, megasecond
    raise ValueError(f"Pandas Timedelta does not natively support {ome_unit.value}")


def ome_image_info(im: Image) -> Dict:
    channels = im.pixels.channels

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
    ts_diff = pd.to_timedelta(im.pixels.time_increment, unit=to_pandas_unit(im.pixels.time_increment_unit)) \
        if im.pixels.time_increment is not None else np.nan

    # failback estimation in case no time_increment was registred
    # assume time in microseconds.
    if np.isnan(ts_diff):  # estimate difference from plane timestamps
        tsmps = list()
        for pl in im.pixels.planes:
            ch_id = channels[pl.the_c].id
            tsmps.append({
                "frame":   pl.the_t,
                "channel": pl.the_c,
                "z":       pl.the_z,
                "dt":      pl.delta_t,
                "dt_unit": pl.delta_t_unit
            })
        tsdf = pd.DataFrame(tsmps)
        unit = tsdf["dt_unit"].unique()
        if len(unit) > 1:
            raise NotImplementedError("Can't deal with the case of different time units in OME plane information yet")
        unit = unit[0]
        # obtain a dataframe considering the first slice of every timepoint and extract the time of capture
        ts_frame = (
            tsdf
            .query("z==0")
            .groupby("channel")["dt"]
            .diff()
            .apply(lambda y: np.nan if y < 0 else y)
            .apply(pd.to_timedelta, unit=to_pandas_unit(unit))
        )
        dt_avg, dt_dev = ts_frame.mean(), ts_frame.std()
        dt_c = dt_dev.components
        if dt_c.hours > 0 or dt_c.minutes > 0 or dt_c.seconds > 0:
            raise ValueError("Time deviation is too large to faithfully represent time stamps in the rendering")
        ts_diff = dt_avg

    assert size_x_unit == size_y_unit == size_z_unit
    if len(im.instrument_ref.ref.objectives) > 0:
        objective = im.instrument_ref.ref.objectives[0]
        objective_id = f"{int(objective.nominal_magnification)}X/{objective.lens_na}" if (
                objective.nominal_magnification is not None and objective.lens_na is not None) else "N/A"
        mag = int(objective.nominal_magnification) if objective.nominal_magnification is not None else np.nan
    else:
        objective_id = "N/A"
        mag = np.nan
    return {
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
    }


def ome_info(md_ome: OME) -> Iterable[Dict]:
    if md_ome is None:
        raise ValueError

    earliest_aquisition = min(im.acquisition_date for im in md_ome.images)
    if earliest_aquisition is not None:
        earliest_aquisition = earliest_aquisition.strftime("%a %b/%d/%Y, %H:%M:%S")

    for im in md_ome.images:
        nfo = ome_image_info(im)
        if isinstance(nfo['delta_t'], timedelta):  # pass to float number representing seconds
            nfo['delta_t'] = nfo['delta_t'].seconds + nfo['delta_t'].microseconds / 10 ** 6

        nfo.update({'acquisition': earliest_aquisition})
        yield nfo
