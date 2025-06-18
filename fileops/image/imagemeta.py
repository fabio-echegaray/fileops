from collections import namedtuple

import numpy as np

MetadataImage = namedtuple('MetadataImage', ['reader', 'image', 'pix_per_um', 'um_per_pix',
                                             'time_interval', 'frame', 'channel',
                                             'z', 'width', 'height',
                                             'timestamp', 'intensity_range'])

MetadataImageSeries = namedtuple('MetadataImageSeries', ['reader', 'images',
                                                         'pix_per_um', 'um_per_pix', 'um_per_z',
                                                         'time_interval', 'frames', 'channels',
                                                         'zstacks', 'width', 'height', 'series',
                                                         'timestamps', 'intensity_ranges', 'axes'])


def metadataimage_like(mdi: MetadataImage, image: np.array):
    return MetadataImage(reader=mdi.reader,
                         image=image,
                         pix_per_um=mdi.pix_per_um,
                         um_per_pix=mdi.um_per_pix,
                         time_interval=mdi.time_interval,
                         timestamp=mdi.timestamp,
                         frame=mdi.frame,
                         channel=mdi.channel,
                         z=mdi.z,
                         width=mdi.width,
                         height=mdi.height,
                         intensity_range=mdi.intensity_range)
