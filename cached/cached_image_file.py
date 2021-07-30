import os
import pathlib
from datetime import datetime
from typing import List

import numpy as np
import pandas as pd
from xml.etree import ElementTree as ET

from imagemeta import MetadataImageSeries, MetadataImage
from .image_loader import load_tiff
from pathutils import ensure_dir
from logger import get_logger


class CachedImageFile:
    ome_ns = {'ome': 'http://www.openmicroscopy.org/Schemas/OME/2016-06'}
    log = get_logger(name='CachedImageFile')

    def __init__(self, image_path: str, image_series=0, cache_results=True, **kwargs):
        self.image_path = os.path.abspath(image_path)
        self.base_path = os.path.dirname(self.image_path)
        self.cache_path = os.path.join(self.base_path, '_cache')
        self.render_path = os.path.join(self.cache_path, 'out', 'render')
        self._use_cache = cache_results
        self._jvm_on = False

        self.metadata_path = os.path.join(self.cache_path, 'ome_image_info.xml')
        self.md = self._get_metadata()
        self._series = image_series
        self.all_series = self.md.findall('ome:Image', self.ome_ns)
        self.instrument_md = self.md.findall('ome:Instrument', self.ome_ns)
        self.objectives_md = self.md.findall('ome:Instrument/ome:Objective', self.ome_ns)

        self.images_md = None
        self.planes_md = None
        self.all_planes = None

        self.timestamps = None
        self.channels = None
        self.stacks = None
        self.frames = None
        self.um_per_pix = None
        self.pix_per_um = None
        self.width = None
        self.height = None
        self._load_imageseries()

        if self._use_cache:
            ensure_dir(self.metadata_path)
            ensure_dir(self.render_path)

        super(CachedImageFile, self).__init__(**kwargs)

    def _check_jvm(self):
        if not self._jvm_on:
            import javabridge
            import bioformats as bf

            self._jvm_on = True
            javabridge.start_vm(class_path=bf.JARS, run_headless=True)

            """This is so that Javabridge doesn't spill out a lot of DEBUG messages
            during runtime.
            From CellProfiler/python-bioformats.
            """
            root_logger_name = javabridge.get_static_field("org/slf4j/Logger",
                                                           "ROOT_LOGGER_NAME",
                                                           "Ljava/lang/String;")
            root_logger = javabridge.static_call("org/slf4j/LoggerFactory",
                                                 "getLogger",
                                                 "(Ljava/lang/String;)Lorg/slf4j/Logger;",
                                                 root_logger_name)
            log_level = javabridge.get_static_field("ch/qos/logback/classic/Level",
                                                    "WARN",
                                                    "Lch/qos/logback/classic/Level;")
            javabridge.call(root_logger,
                            "setLevel",
                            "(Lch/qos/logback/classic/Level;)V",
                            log_level)

    @property
    def info(self) -> pd.DataFrame:
        fname_stat = pathlib.Path(self.image_path).stat()
        fcreated = datetime.fromtimestamp(fname_stat.st_ctime).strftime("%a %b/%d/%Y, %H:%M:%S")
        fmodified = datetime.fromtimestamp(fname_stat.st_mtime).strftime("%a %b/%d/%Y, %H:%M:%S")
        series_info = list()
        for imageseries in self.md.findall('ome:Image', self.ome_ns):
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
                    'magnification':                     objective.get('NominalMagnification'),
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
        return self._series

    @series.setter
    def series(self, s):
        if type(s) == int:
            self._series = s
            self._load_imageseries()
        elif type(s) == str:
            for k, imser in enumerate(self.all_series):
                if imser.attrib['Name'] == s:
                    self._series = k
                    self._load_imageseries()
        else:
            raise ValueError("Unexpected type of variable to load series.")

    def _load_imageseries(self):
        self.images_md = self.all_series[self._series]
        self.planes_md = self.images_md.find('ome:Pixels', self.ome_ns)
        self.all_planes = self.images_md.findall('ome:Pixels/ome:Plane', self.ome_ns)

        self.timestamps = sorted(np.unique([p.get('DeltaT') for p in self.all_planes]).astype(np.float64))
        self.time_interval = np.mean(np.diff(self.timestamps))
        self.channels = sorted(np.unique([p.get('TheC') for p in self.all_planes]).astype(int))
        self.stacks = sorted(np.unique([p.get('TheZ') for p in self.all_planes]).astype(int))
        self.frames = sorted(np.unique([p.get('TheT') for p in self.all_planes]).astype(int))
        self.um_per_pix = float(self.planes_md.get('PhysicalSizeX')) if \
            self.planes_md.get('PhysicalSizeX') == self.planes_md.get('PhysicalSizeY') else np.nan
        self.pix_per_um = 1. / self.um_per_pix
        self.width = int(self.planes_md.get('SizeX'))
        self.height = int(self.planes_md.get('SizeY'))

        self.log.info(f"{len(self.all_planes)} image planes in total.")

    def ix_at(self, c, z, t):
        for i, plane in enumerate(self.all_planes):
            if int(plane.get('TheC')) == c and int(plane.get('TheZ')) == z and int(plane.get('TheT')) == t:
                return i

    def image(self, *args) -> MetadataImage:
        if len(args) == 1 and isinstance(args[0], int):
            ix = args[0]
            plane = self.all_planes[ix]
            return self._image(plane, row=0, col=0, fid=0)

    def images(self, channel=0, zstack=0) -> List[np.ndarray]:
        for t in self.frames:
            ix = self.ix_at(channel, zstack, t)
            plane = self.all_planes[ix]
            yield self._image(plane, row=0, col=0, fid=0).image

    def image_series(self, channel=0, zstack=0) -> MetadataImageSeries:
        images = list()
        for t in self.frames:
            ix = self.ix_at(channel, zstack, t)
            plane = self.all_planes[ix]
            images.append(self._image(plane, row=0, col=0, fid=0).image)
        return MetadataImageSeries(images=np.asarray(images), pix_per_um=self.pix_per_um, um_per_pix=self.um_per_pix,
                                   frames=len(self.frames), timestamps=len(self.frames),
                                   time_interval=self.time_interval,
                                   channels=len(self.channels), zstacks=len(self.stacks),
                                   width=self.width, height=self.height,
                                   series=None, intensity_ranges=None)

    def _image(self, plane, row=0, col=0, fid=0) -> MetadataImage:
        c, z, t = plane.get('TheC'), plane.get('TheZ'), plane.get('TheT')
        # logger.debug('retrieving image id=%d row=%d col=%d fid=%d' % (_id, row, col, fid))
        # check if file is in cache
        fname = f"{row}{col}{fid}-{c}{z}{t}.tif"
        fpath = os.path.join(self.cache_path, fname)
        if os.path.exists(fpath) and self._use_cache:
            self.log.debug(f"Loading image {fname} from cache.")
            tiff = load_tiff(fpath)
            image = tiff.image[0]
        else:
            self.log.debug("Loading image from original file (starts JVM if not on).")
            import bioformats as bf
            from tifffile import imsave
            self._check_jvm()
            reader = bf.ImageReader(self.image_path, perform_init=True)
            image = reader.read(c=c, z=z, t=t, series=self.series, rescale=False)
            if self._use_cache:
                self.log.debug(f"Saving image {fname} in cache (path={fpath}).")
                imsave(fpath, np.array(image))

        return MetadataImage(image=image, pix_per_um=1. / self.um_per_pix, um_per_pix=self.um_per_pix,
                             time_interval=None, timestamp=float(plane.get('DeltaT')),
                             frame=int(t), channel=int(c), z=int(z),
                             width=int(self.planes_md.get('SizeX')), height=int(self.planes_md.get('SizeY')),
                             intensity_range=[np.min(image), np.max(image)])

    def _get_metadata(self):
        self._check_jvm()

        self.log.debug(f"metadata_path is {self.metadata_path}.")
        if not os.path.exists(self.metadata_path):
            import bioformats as bf
            md = bf.get_omexml_metadata(self.image_path)

            if self._use_cache:
                self.log.warning("File ome_image_info.xml is missing in the folder structure, generating it now.\r\n"
                                 "\tNew folders with the names '_cache' will be created. "
                                 "You can safely delete this folder if you don't want \n\n"
                                 "any of the analysis output from this tool.\r\n")

                with open(self.metadata_path, 'w') as mdf:
                    mdf.write(md)

            md = ET.fromstring(md.encode("utf-8"))

        else:
            self.log.debug("Loading metadata from file in cache.")
            with open(self.metadata_path, 'r') as mdf:
                md = ET.parse(mdf)

        return md