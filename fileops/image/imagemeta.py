from collections import namedtuple

MetadataImage = namedtuple('MetadataImage', ['reader', 'image', 'pix_per_um', 'um_per_pix',
                                             'time_interval', 'frame', 'channel',
                                             'z', 'width', 'height',
                                             'timestamp', 'intensity_range'])

MetadataImageSeries = namedtuple('MetadataImageSeries', ['reader', 'images', 'pix_per_um', 'um_per_pix',
                                                         'time_interval', 'frames', 'channels',
                                                         'zstacks', 'width', 'height', 'series',
                                                         'timestamps', 'intensity_ranges'])
