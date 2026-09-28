from collections.abc import Iterable

import numpy as np
from tifffile import TiffFileError

from fileops.image import to_8bit
from fileops.image.exceptions import FrameNotFoundError
from fileops.image.imagemeta import MetadataImage
from ._z_projection_types import ZProjection, zprojection_from_str


def depth_field(im_vol: np.ndarray) -> np.ndarray:
    """ Computes depth data of a normalized z-stack volume

    For every pixel, returns where along the stack (0.0 = bottom, 1.0 = top)
    the pixel is brightest.

    Returns a (height, width) float array with values in [0, 1].
    """
    n_z = im_vol.shape[0]
    im_max = np.max(im_vol, axis=0)
    if n_z <= 1:
        return np.zeros(im_max.shape, dtype=float)
    z_idx = np.argmax(im_vol, axis=0)
    return z_idx / (n_z - 1)


def _read_planes(img_file, frame: int, channel: int, z_subset=None, as_8bit=False) -> list:
    """Read the z-planes of one channel+frame into a list of arrays."""
    images = list()
    zstack = z_subset if z_subset is not None and isinstance(z_subset, Iterable) else range(img_file.n_zstacks)
    for zs in zstack:
        try:
            if img_file.ix_at(channel, zs, frame) is not None:
                plane = img_file.plane_at(channel, zs, frame)
                img = img_file._image(plane).image
                images.append(to_8bit.to_8bit(img) if as_8bit else img)
        except FrameNotFoundError as e:
            img_file.log.error(f"image at t={frame} c={channel} z={zs} not found in file")
            raise e
        except TypeError as e:
            raise
        except (IndexError, TiffFileError) as e:
            raise FrameNotFoundError(
                f"image not found in the file at t={frame} c={channel} z={zs} (error raised was: {str(e)}).")
        except KeyError as e:
            img_file.log.error(f"internal class error at t={frame} c={channel} z={zs} (error raised was: {str(e)}).")
            raise FrameNotFoundError(
                f"internal class error at t={frame} c={channel} z={zs} (error raised was: {str(e)}).")
    return images


def z_volume(img_file, frame: int, channel: int, z_subset=None, as_8bit=False) -> np.ndarray:
    """Assemble the z-planes of one channel+frame into a ``(n_z, H, W)`` volume.

    Pure data assembly: returns the raw stack so derived measurements (e.g.
    ``depth_field``) can be computed on it.  Depth-coded *rendering* (mapping
    the stack to colours) is not a projection type and is not part of this
    package; it is handled by the caller (e.g. MovieRender).
    """
    images = _read_planes(img_file, frame, channel, z_subset=z_subset, as_8bit=as_8bit)
    img_file.log.debug(f"retrieved {len(images)} images at frame {frame}")
    if len(images) == 0:
        img_file.log.error(f"not able to read a z-stack at t={frame} c={channel}")
        raise FrameNotFoundError(f"z_volume was not able to assemble a z-stack at t={frame} c={channel}")
    try:
        return np.asarray(images).reshape((len(images), *images[-1].shape))
    except ValueError as e:
        img_file.log.error(e)
        raise FrameNotFoundError


def z_projection(img_file, frame: int, channel: int, projection='max', z_subset=None, as_8bit=False) -> MetadataImage:
    img_file.log.debug(f"executing z-{projection}-projection of frame {frame} and channel {channel}")

    im_vol = z_volume(img_file, frame, channel, z_subset=z_subset, as_8bit=as_8bit)
    _reader = 'def_proj'
    zprj = zprojection_from_str(projection) if type(projection) == str else projection
    if zprj == ZProjection.MAX:
        _reader = 'MaxProj'
        im_proj = np.max(im_vol, axis=0)
    elif zprj == ZProjection.MIN:
        _reader = 'MinProj'
        im_proj = np.min(im_vol, axis=0)
    elif zprj == ZProjection.SUM:
        _reader = 'SumProj'
        im_proj = np.sum(im_vol, axis=0)
    elif zprj == ZProjection.STD:
        _reader = 'StdDevProj'
        im_proj = np.std(im_vol, axis=0)
    elif zprj == ZProjection.MEAN:
        _reader = 'AvgProj'
        im_proj = np.mean(im_vol, axis=0)
    elif zprj == ZProjection.MEDIAN:
        _reader = 'MedianProj'
        im_proj = np.median(im_vol, axis=0)
    else:
        im_proj = np.zeros_like(im_vol[0])

    try:
        immin, immax = np.min(im_proj), np.max(im_proj)
    except ValueError as e:
        img_file.log.error(e)
        raise FrameNotFoundError

    return MetadataImage(reader=_reader,
                         image=im_proj,
                         pix_per_um=img_file.pix_per_um, um_per_pix=img_file.um_per_pix,
                         frame=frame, timestamp=None, time_interval=None,
                         channel=channel, z=zprj.value,
                         width=img_file.width, height=img_file.height,
                         intensity_range=[immin, immax])
