import os
import io
import xml.etree
import xml.etree.ElementTree
from typing import List

import numpy as np
import pandas as pd
from PIL import Image
import tifffile as tf
import skimage.draw as draw
from czifile import CziFile
from shapely.geometry import Polygon

import logger
from cached import CachedImageFile
from imagemeta import MetadataImage, MetadataImageSeries

log = logger.get_logger(__name__)


def integral_over_surface(image, polygon):
    c, r = polygon.boundary.xy
    rr, cc = draw.polygon(r, c)

    try:
        ss = np.sum(image[rr, cc])
        return ss
    except Exception:
        log.warning('integral_over_surface measured incorrectly')
        return np.nan


def generate_mask_from(polygon: Polygon, shape=None):
    if shape is None:
        minx, miny, maxx, maxy = polygon.bounds
        image = np.zeros((maxx - minx, maxy - miny), dtype=np.bool)
    else:
        image = np.zeros(shape, dtype=np.bool)

    c, r = polygon.boundary.xy
    rr, cc = draw.polygon(r, c)
    image[rr, cc] = True
    return image


def load_tiff(file_or_path) -> MetadataImageSeries:
    if type(file_or_path) == str:
        _, img_name = os.path.split(file_or_path)
    if issubclass(type(file_or_path), io.BufferedIOBase):
        _, img_name = os.path.split(file_or_path.name)

    res = None
    with tf.TiffFile(file_or_path) as tif:
        assert len(tif.series) == 1, "Not currently handled."
        idx = tif.series[0].axes
        width = tif.series[0].shape[idx.find('X')]
        height = tif.series[0].shape[idx.find('Y')]

        if tif.is_imagej is not None:
            metadata = {}
            if tif.imagej_metadata is not None:
                metadata = tif.imagej_metadata

            dt = metadata['finterval'] if 'finterval' in metadata else None

            # asuming square pixels
            if 'XResolution' in tif.pages[0].tags:
                xr = tif.pages[0].tags['XResolution'].value
                res = float(xr[0]) / float(xr[1])  # pixels per um
                if tif.pages[0].tags['ResolutionUnit'].value == 'CENTIMETER':
                    res = res / 1e4

            images = None
            if len(tif.pages) == 1:
                if ('slices' in metadata and metadata['slices'] > 1) or (
                        'frames' in metadata and metadata['frames'] > 1):
                    images = tif.pages[0].asarray()
                else:
                    images = [tif.pages[0].asarray()]
            elif len(tif.pages) > 1:
                images = list()
                for i, page in enumerate(tif.pages):
                    images.append(page.asarray())

            ax_dct = {n: k for k, n in enumerate(tif.series[0].axes)}
            shape = tif.series[0].shape
            frames = metadata['frames'] if 'frames' in metadata else 1
            ts = np.linspace(start=0, stop=frames * dt, num=frames) if dt is not None else None
            return MetadataImageSeries(images=np.asarray(images), pix_per_um=res, um_per_pix=1. / res,
                                       time_interval=dt, frames=frames, timestamps=ts,
                                       channels=metadata['channels'] if 'channels' in metadata else 1,
                                       zstacks=shape[ax_dct['Z']] if 'Z' in ax_dct else 1,
                                       width=width, height=height, series=tif.series[0],
                                       intensity_ranges=metadata['Ranges'] if 'Ranges' in metadata else None)


def load_zeiss(path):
    _, img_name = os.path.split(path)
    with CziFile(path) as czi:
        xmltxt = czi.metadata()
        meta = xml.etree.ElementTree.fromstring(xmltxt)

        # next line is somewhat cryptic, but just extracts um/pix (calibration) of X and Y into res
        res = [float(i[0].text) for i in meta.findall('.//Scaling/Items/*') if
               i.attrib['Id'] == 'X' or i.attrib['Id'] == 'Y']
        assert res[0] == res[1], "pixels are not square"

        # get first calibration value and convert it from meters to um
        res = res[0] * 1e6

        ts_ix = [k for k, a1 in enumerate(czi.attachment_directory) if a1.filename[:10] == 'TimeStamps'][0]
        timestamps = list(czi.attachments())[ts_ix].data()
        dt = np.median(np.diff(timestamps))

        ax_dct = {n: k for k, n in enumerate(czi.axes)}
        n_frames = czi.shape[ax_dct['T']]
        n_slices = czi.shape[ax_dct['Z']]
        n_channels = czi.shape[ax_dct['C']]
        n_X = czi.shape[ax_dct['X']]
        n_Y = czi.shape[ax_dct['Y']]

        images = list()
        for sb in czi.subblock_directory:
            images.append(sb.data_segment().data().reshape((n_X, n_Y)))

        return MetadataImage(image=np.array(images), pix_per_um=1. / res, um_per_pix=res, time_interval=dt,
                             frames=n_frames, z_stacks=n_slices, channels=n_channels,
                             width=n_X, height=n_Y, series=None)


def find_image(img_name, folder=None):
    if folder is None:
        folder = os.path.dirname(img_name)
        img_name = os.path.basename(img_name)

    for root, directories, filenames in os.walk(folder):
        for file in filenames:
            joinf = os.path.abspath(os.path.join(root, file))
            if os.path.isfile(joinf) and joinf[-4:] == '.tif' and file == img_name:
                return load_tiff(joinf)
            if os.path.isfile(joinf) and joinf[-4:] == '.czi' and file == img_name:
                return load_zeiss(joinf)


def retrieve_image(image_arr, frame, channel=0, number_of_frames=1):
    nimgs = image_arr.shape[0]
    n_channels = int(nimgs / number_of_frames)
    ix = frame * n_channels + channel
    log.debug("Retrieving frame %d of channel %d (index=%d)" % (frame, channel, ix))
    return image_arr[ix]


def retrieve_from_pageseries(series: tf.tifffile.TiffPageSeries, frame, channel=0, zstack=0):
    idx = series.axes
    assert idx == 'TZCYX' or idx == 'TCYX', "Can't handle series at the moment (got %s)." % idx
    # logger.debug("Retrieving frame %d of channel %d (index=%d)" % (frame, channel, ix))
    # width = series.shape[idx.find('X')]
    # height = series.shape[idx.find('Y')]
    out = np.empty(0)
    if idx == 'TZCYX':
        out = series.asarray()[frame, zstack, channel, :, :]
    elif idx == 'TCYX':
        out = series.asarray()[frame, channel, :, :]
    elif idx == 'TZYX':
        out = series.asarray()[frame, zstack, :, :]
    # if channel == 'all':
    #     channel = slice(series.shape[idx.find('C')])
    # if zstack == 'all':
    #     zstack = slice(series.shape[idx.find('Z')])
    return out


def image_iterator(image_arr, channel=0, zstack=0, number_of_frames=1, number_of_zstacks=1, number_of_channels=1):
    nimgs = image_arr.shape[0]
    for f in range(number_of_frames):
        ix = f * number_of_channels + zstack * number_of_zstacks + channel
        log.debug("retrieving frame %d of channel %d (index=%d)" % (f, channel, ix))
        if ix < nimgs:
            yield image_arr[ix]


def mask_iterator(image_it, mask_lst):
    for fr, img in enumerate(image_it):
        for _fr, msk in mask_lst:
            if fr != _fr: continue
            msk_img = generate_mask_from(msk, shape=img.shape)
            yield img * msk_img


def masked_image(img: np.array, mask_lst: List[Polygon]):
    mask_img = np.zeros(img.shape, dtype=np.uint8)
    for mask in mask_lst:
        c, r = mask.boundary.xy
        rr, cc = draw.polygon(r, c)
        mask_img[rr, cc] = 1
    img = img * mask_img
    # img = np.ma.masked_where(mask_img, img)
    return img


def pil_grid(images, max_horiz=np.iinfo(int).max):
    n_images = len(images)
    n_horiz = min(n_images, max_horiz)
    h_sizes, v_sizes = [0] * n_horiz, [0] * (n_images // n_horiz)
    for i, im in enumerate(images):
        h, v = i % n_horiz, i // n_horiz
        h_sizes[h] = max(h_sizes[h], im.size[0])
        v_sizes[v] = max(v_sizes[v], im.size[1])
    h_sizes, v_sizes = np.cumsum([0] + h_sizes), np.cumsum([0] + v_sizes)
    im_grid = Image.new('RGB', (h_sizes[-1], v_sizes[-1]), color='white')
    for i, im in enumerate(images):
        im_grid.paste(im, (h_sizes[i % n_horiz], v_sizes[i // n_horiz]))
    return im_grid


def canvas_to_pil(canvas):
    canvas.draw()
    s = canvas.tostring_rgb()
    w, h = canvas.get_width_height()[::-1]
    im = Image.frombytes("RGB", (w, h), s)
    return im


def image_list(folder: str):
    folder_list = list()
    for root, directories, filenames in os.walk(folder):
        common = os.path.relpath(root, start=folder)
        for file in filenames:
            joinf = os.path.abspath(os.path.join(root, file))
            ext = joinf[-4:]
            name = os.path.basename(joinf)
            if os.path.isfile(joinf) and ext == '.tif':
                tiffmd = load_tiff(joinf)
                folder_list.append({
                    'name':            name,
                    'folder':          common,
                    'resolution':      tiffmd.pix_per_um,
                    'meta_img_shape':  tiffmd.image.shape,
                    'width':           tiffmd.width,
                    'height':          tiffmd.height,
                    'time_interval':   tiffmd.time_interval,
                    'number_frames':   tiffmd.frames,
                    'number_channels': tiffmd.channels,
                })
    df = pd.DataFrame(folder_list)
    df.to_csv(os.path.join(folder, os.path.basename(folder) + "summary.csv"))
    return df


class ImageMixin:
    log = None

    def __init__(self, filename, **kwargs):
        self.log.debug("ImageMixin init.")
        self.filename = filename

        self._c = CachedImageFile(filename, cache_results=False)

        # self.log.info(f"Image retrieved has axes format {self.series.axes}")
        super().__init__(**kwargs)

    def _load_tiff(self):
        self._f = open(self.filename, 'rb')
        im = load_tiff(self._f)
        self.images = im.image
        self.series = im.series
        self.pix_per_um = im.pix_per_um
        self.um_per_pix = im.um_per_pix
        self.dt = im.time_interval
        self.frames = im.frames
        self.timestamps = None
        self.stacks = im.zstacks
        self.channels = im.channels
        self.width = im.width
        self.height = im.height
        self._image_file = os.path.basename(self.filename)
        self._image_path = os.path.dirname(self.filename)

    def __del__(self):
        if hasattr(self, '_f') and self._f is not None:
            self._f.close()

    def max_projection(self, frame=None, channel=None):
        if frame is None:
            pass
        elif self.series.axes == 'TCYX':
            if channel is None:
                return self.series.asarray()[frame, :, :, :]
            else:
                return self.series.asarray()[frame, channel, :, :]
