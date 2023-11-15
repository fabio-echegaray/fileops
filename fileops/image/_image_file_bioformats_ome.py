import os
import xml.etree.ElementTree
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree as ET

import bioformats as bf
import numpy as np
import pandas as pd

from fileops.image._base import ImageFileBase
from fileops.image.imagemeta import MetadataImage
from fileops.image.javabridge import create_jvm
from fileops.logger import get_logger


class OMEImageFile(ImageFileBase):
    ome_ns = {'ome': 'http://www.openmicroscopy.org/Schemas/OME/2016-06'}
    log = get_logger(name='OMEImageFile')

    def __init__(self, image_path: Path, jvm=None, **kwargs):
        super().__init__(image_path, **kwargs)

        self._jvm = jvm
        self._rdr: bf.ImageReader = None

        self.md, self.md_xml = self._get_metadata()
        self.all_series = self.md.findall('ome:Image', self.ome_ns)
        self.instrument_md = self.md.findall('ome:Instrument', self.ome_ns)
        self.objectives_md = self.md.findall('ome:Instrument/ome:Objective', self.ome_ns)

        self._load_imageseries()

        if not self.timestamps:
            self.time_interval = self.failover_dt
            self.timestamps = [self.failover_dt * f for f in self.frames]

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

    @property
    def series(self):
        return self.all_series[self._series]

    @series.setter
    def series(self, s):
        if type(s) == int:
            self._series = s
        elif type(s) == str:
            for k, imser in enumerate(self.all_series):
                if imser.attrib['Name'] == s:
                    self._series = k
                    break
        elif type(s) == xml.etree.ElementTree.Element:
            for k, imser in enumerate(self.all_series):
                if imser.attrib == s.attrib:
                    self._series = k
                    break
        else:
            raise ValueError("Unexpected type of variable to load series.")

        super().__init__(s)

    def _load_imageseries(self):
        if not self.all_series:
            return
        self.images_md = self.all_series[self._series]
        self.planes_md = self.images_md.find('ome:Pixels', self.ome_ns)
        self.all_planes = self.images_md.findall('ome:Pixels/ome:Plane', self.ome_ns)

        self.channels = set(int(p.get('TheC')) for p in self.all_planes)
        self.zstacks = sorted(np.unique([p.get('TheZ') for p in self.all_planes]).astype(int))
        self.frames = sorted(np.unique([p.get('TheT') for p in self.all_planes]).astype(int))
        self.n_channels = len(self.channels)
        self.n_zstacks = len(self.zstacks)
        self.n_frames = len(self.frames)
        self.um_per_pix = float(self.planes_md.get('PhysicalSizeX')) if \
            self.planes_md.get('PhysicalSizeX') == self.planes_md.get('PhysicalSizeY') else np.nan
        self.pix_per_um = 1. / self.um_per_pix
        self.width = int(self.planes_md.get('SizeX'))
        self.height = int(self.planes_md.get('SizeY'))
        self.um_per_z = float(self.planes_md.get('PhysicalSizeZ')) if self.planes_md.get('PhysicalSizeZ') else None

        obj = self.images_md.find('ome:ObjectiveSettings', self.ome_ns)
        obj_id = obj.get('ID') if obj else None
        objective = self.md.find(f'ome:Instrument/ome:Objective[@ID="{obj_id}"]', self.ome_ns) if obj else None
        self.magnification = int(float(objective.get('NominalMagnification'))) if objective else None

        self.timestamps = sorted(
            np.unique([p.get('DeltaT') for p in self.all_planes if p.get('DeltaT') is not None]).astype(np.float64))
        self.time_interval = np.mean(np.diff(self.timestamps))

        # build dictionary where the keys are combinations of c z t and values are the index
        self.all_planes_md_dict = {f"{int(plane.get('TheC')):0{len(str(self.n_channels))}d}"
                                   f"{int(plane.get('TheZ')):0{len(str(self.n_zstacks))}d}"
                                   f"{int(plane.get('TheT')):0{len(str(self.n_frames))}d}": i
                                   for i, plane in enumerate(self.all_planes)}

        self.log.info(f"Image series {self._series} loaded. "
                      f"Image size (WxH)=({self.width:d}x{self.height:d}); "
                      f"calibration is {self.pix_per_um:0.3f} pix/um and {self.um_per_z:0.3f} um/z-step; "
                      f"movie has {len(self.frames)} frames, {self.n_channels} channels, {self.n_zstacks} z-stacks and "
                      f"{len(self.all_planes)} image planes in total.")

    def _lazy_load_jvm(self):
        if not self._jvm:
            self._jvm = create_jvm()
        if not self._rdr:
            self._rdr = bf.ImageReader(self.image_path.as_posix(), perform_init=True)

    def _image(self, plane, row=0, col=0, fid=0) -> MetadataImage:  # PLANE HAS METADATA INFO OF THE IMAGE PLANE
        c, z, t = plane.get('TheC'), plane.get('TheZ'), plane.get('TheT')
        # logger.debug('retrieving image id=%d row=%d col=%d fid=%d' % (_id, row, col, fid))
        self._lazy_load_jvm()

        image = self._rdr.read(c=c, z=z, t=t, series=self._series, rescale=False)
        bf.clear_image_reader_cache()

        w = int(self.planes_md.get('SizeX'))
        h = int(self.planes_md.get('SizeY'))

        return MetadataImage(reader='OME',
                             image=image,
                             pix_per_um=1. / self.um_per_pix, um_per_pix=self.um_per_pix,
                             time_interval=None,
                             timestamp=float(plane.get('DeltaT')) if plane.get('DeltaT') is not None else 0.0,
                             frame=int(t), channel=int(c), z=int(z), width=w, height=h,
                             intensity_range=[np.min(image), np.max(image)])

    def _get_metadata(self):
        self._lazy_load_jvm()

        md_xml = bf.get_omexml_metadata(self.image_path.as_posix())
        md = ET.fromstring(md_xml.encode("utf-8"))

        return md, md_xml
