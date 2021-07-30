from collections import namedtuple

MetadataImage = namedtuple('MetadataImage', ['image', 'pix_per_um', 'um_per_pix',
                                             'time_interval', 'frame', 'channel',
                                             'z', 'width', 'height',
                                             'timestamp', 'intensity_range'])

MetadataImageSeries = namedtuple('MetadataImageSeries', ['images', 'pix_per_um', 'um_per_pix',
                                                         'time_interval', 'frames', 'channels',
                                                         'zstacks', 'width', 'height', 'series',
                                                         'timestamps', 'intensity_ranges'])
