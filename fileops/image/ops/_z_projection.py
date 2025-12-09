import numpy as np
from fileops.image import to_8bit
from fileops.image.exceptions import FrameNotFoundError
from fileops.image.imagemeta import MetadataImage

from ._z_projection_types import ZProjection, zprojection_from_str


def z_projection(img_file, frame: int, channel: int, projection='max', as_8bit=False):
    img_file.log.debug(f"executing z-{projection}-projection of frame {frame} and channel {channel}")

    images = list()

    for zs in range(img_file.n_zstacks):
        try:
            if img_file.ix_at(channel, zs, frame) is not None:
                plane = img_file.plane_at(channel, zs, frame)
                img = img_file._image(plane).image
                images.append(to_8bit(img) if as_8bit else img)
        except FrameNotFoundError as e:
            img_file.log.error(f"image at t={frame} c={channel} z={zs} not found in file.")
            raise e
        except IndexError as e:
            raise FrameNotFoundError(f"image not found in the file at t={frame} c={channel} z={zs}.")
        except KeyError as e:
            img_file.log.error(f"internal class error at t={frame} c={channel} z={zs}.")
            raise e

    if len(images) == 0:
        img_file.log.error(f"not able to make a z-projection at t={frame} c={channel}.")
        raise FrameNotFoundError

    im_vol = np.asarray(images).reshape((len(images), *images[-1].shape))
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
        im_proj = np.zeros_like(images[0])
    return MetadataImage(reader=_reader,
                         image=im_proj,
                         pix_per_um=img_file.pix_per_um, um_per_pix=img_file.um_per_pix,
                         frame=frame, timestamp=None, time_interval=None,
                         channel=channel, z=None,
                         width=img_file.width, height=img_file.height,
                         intensity_range=[np.min(im_proj), np.max(im_proj)])
