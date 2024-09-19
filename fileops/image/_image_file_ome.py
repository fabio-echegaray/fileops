import os
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from fileops.image.image_file import ImageFile
from fileops.logger import get_logger


class OMEImageFile(ImageFile):
    ome_ns = {'ome': 'http://www.openmicroscopy.org/Schemas/OME/2016-06'}
    log = get_logger(name='OMEImageFile')

    def __init__(self, image_path: Path, **kwargs):
        super(OMEImageFile, self).__init__(image_path, **kwargs)

        self.md = None
        self.md_xml = None
        self.all_series = None
        self.instrument_md = None
        self.objectives_md = None
        self.md_description = None

        self._load_imageseries()

        self._fix_defaults(failover_dt=self._failover_dt, failover_mag=self._failover_mag)

    @property
    def info(self) -> pd.DataFrame:
        fname_stat = Path(self.image_path).stat()
        fcreated = datetime.fromtimestamp(fname_stat.st_ctime).strftime("%a %b/%d/%Y, %H:%M:%S")
        fmodified = datetime.fromtimestamp(fname_stat.st_mtime).strftime("%a %b/%d/%Y, %H:%M:%S")
        series_info = list()
        for imageseries in self.md.findall('ome:Image', self.ome_ns):  # iterate through all series
            instrument = imageseries.find('ome:InstrumentRef', self.ome_ns)
            obj_id = imageseries.find('ome:ObjectiveSettings', self.ome_ns).get('ID')
            objective = self.md.find(f'ome:Instrument/ome:Objective[@ID="{obj_id}"]', self.ome_ns)
            imgseries_pixels = imageseries.findall('ome:Pixels', self.ome_ns)
            for isr_pixels in imgseries_pixels:
                size_x = float(isr_pixels.get('PhysicalSizeX'))
                size_y = float(isr_pixels.get('PhysicalSizeY'))
                size_z = float(isr_pixels.get('PhysicalSizeZ'))
                size_x_unit = isr_pixels.get('PhysicalSizeXUnit')
                size_y_unit = isr_pixels.get('PhysicalSizeYUnit')
                size_z_unit = isr_pixels.get('PhysicalSizeZUnit')
                timestamps = sorted(
                    np.unique([p.get('DeltaT') for p in isr_pixels.findall('ome:Plane', self.ome_ns) if
                               p.get('DeltaT') is not None]).astype(np.float64))
                series_info.append({
                    'filename':                          os.path.basename(self.image_path),
                    'image_id':                          imageseries.get('ID'),
                    'image_name':                        imageseries.get('Name'),
                    'instrument_id':                     instrument.get('ID'),
                    'pixels_id':                         isr_pixels.get('ID'),
                    'channels':                          int(isr_pixels.get('SizeC')),
                    'z-stacks':                          int(isr_pixels.get('SizeZ')),
                    'frames':                            int(isr_pixels.get('SizeT')),
                    'delta_t':                           float(np.nanmean(np.diff(timestamps))),
                    # 'timestamps': timestamps,
                    'width':                             self.width,
                    'height':                            self.height,
                    'data_type':                         isr_pixels.get('Type'),
                    'objective_id':                      obj_id,
                    'magnification':                     int(float(objective.get('NominalMagnification'))),
                    'pixel_size':                        (size_x, size_y, size_z),
                    'pixel_size_unit':                   (size_x_unit, size_y_unit, size_z_unit),
                    'pix_per_um':                        (1 / size_x, 1 / size_y, 1 / size_z),
                    'change (Unix), creation (Windows)': fcreated,
                    'most recent modification':          fmodified,
                })
        out = pd.DataFrame(series_info)
        return out
