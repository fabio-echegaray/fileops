import sys
import itertools

import javabridge
import bioformats
import bioformats as bf
import bioformats.omexml as ome
import tifffile as tf
from bioformats.formatreader import ImageReader
from tifffile import tiffcomment


def silence_javabridge_log():
    # Forbid Javabridge to spill out DEBUG messages during runtime from CellProfiler/python-bioformats.
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


def writeplanes(pixel, SizeT=1, SizeZ=1, SizeC=1, order='TZCYX', verbose=False):
    if order == 'TZCYX':
        counter = 0
        for t in range(SizeT):
            for z in range(SizeZ):
                for c in range(SizeC):

                    if verbose:
                        print('Write PlaneTable: ', t, z, c),
                        sys.stdout.flush()

                    pixel.Plane(counter).TheT = t
                    pixel.Plane(counter).TheZ = z
                    pixel.Plane(counter).TheC = c
                    counter = counter + 1

    return pixel


def image_it(frames_per_block, pre_fname, folder, n_files=0, position=0, n_positions=1):
    print(f'image_it n_files={n_files}')

    def fname(i):
        return folder + f'{pre_fname}{"_" + str(i) if i > 0 else ""}.ome.tif'

    frames_of_all_files = 0
    for i in range(n_files):
        o = bf.OMEXML(bf.get_omexml_metadata(path=fname(i)))
        im = o.image(index=0)
        frames_of_all_files += im.Pixels.SizeT

    timepoints_per_position = int(frames_of_all_files / n_positions)
    n_blocks = int(n_positions * timepoints_per_position)
    img_ix_list = [list(range(i * frames_per_block, (i + 1) * frames_per_block))
                   for i in range(n_blocks)
                   if i % n_positions == position]
    img_ix_list = list(itertools.chain(*img_ix_list))
    print(img_ix_list)

    img_count = 0
    for i in range(n_files):
        print(f"file {fname(i)}")
        with ImageReader(fname(i), perform_init=True) as reader:
            # re-read metadata for the specific file
            o = bf.OMEXML(bf.get_omexml_metadata(path=fname(i)))
            im = o.image(index=0)
            for frame in range(im.Pixels.SizeT):
                should_yield = img_count in img_ix_list
                print(f'frame {frame} img_count {img_count} {should_yield}')
                img_count += 1
                if should_yield:
                    image = reader.read(c=0, z=0, t=frame, rescale=False)
                    yield image


if __name__ == "__main__":
    javabridge.start_vm(class_path=bioformats.JARS, run_headless=True)
    silence_javabridge_log()

    # parameters of modular arithmetic
    # to get the correct images of a particular specimen position
    Series = 0
    position = 0
    n_zstacks = 1
    n_positions = 9
    n_channels = 1
    zc = n_zstacks * n_channels
    gap = n_positions * zc

    folder = '/media/lab/Data/Fabio/Nikon/20220117 - SFWT UE/no_treatment_3/'
    pre_fname = 'no_treatment_3_MMStack'
    fname = f"{folder}{pre_fname}.ome.tif"

    # initialize image writer
    out_file = f"{pre_fname}{position}.ome.tif"
    tif = tf.TiffWriter(out_file, imagej=False, bigtiff=True)

    # read image metadata
    o = bf.OMEXML(bf.get_omexml_metadata(path=fname))
    # our weird format would only have one image series; assert this and get image metadata,
    # or throw exception otherwise
    print(f"file has {o.image_count} image series.")
    assert o.image_count == 1, "file has more than one image series."

    im = o.image(index=0)
    print(f"image series has {im.Pixels.SizeC} channels, {im.Pixels.SizeT} frames, "
          f"{im.Pixels.SizeX} px on X dir, {im.Pixels.SizeY} px on Y dir, {im.Pixels.SizeZ} px on Z dir.")
    assert im.Pixels.SizeC == 1 and im.Pixels.SizeZ == 1

    # iterate through all files and get the images of specific position
    pos_frame = 0
    for it_frame, image in enumerate(
            image_it(zc, pre_fname, folder, n_files=154, position=position, n_positions=n_positions)):
        tif.save(image, contiguous=False, photometric='minisblack', metadata={})
        if it_frame % zc == 0:
            pos_frame += 1
        print(f"it_frame -> {it_frame} pos_frame -> {pos_frame}")

    tif.close()

    # update metadata
    print(f'pos_frame {pos_frame} n_channels {n_channels} n_zstacks {n_zstacks}')
    fname = folder + 'no_treatment_3_MMStack.ome.tif'

    SizeX = im.Pixels.SizeX
    SizeY = im.Pixels.SizeY
    SizeC = n_channels
    SizeT = pos_frame
    SizeZ = n_zstacks
    scalex = im.Pixels.PhysicalSizeX
    scaley = im.Pixels.PhysicalSizeY
    scalez = im.Pixels.PhysicalSizeZ
    pixeltype = im.Pixels.PixelType
    dimorder = 'TZCYX'

    # Create metadata info
    omexml = ome.OMEXML()
    omexml.image(Series).Name = out_file
    p = omexml.image(Series).Pixels
    # p.ID = 0
    p.DimensionOrder = im.Pixels.DimensionOrder
    p.SizeX = SizeX
    p.SizeY = SizeY
    p.SizeC = SizeC
    p.SizeT = SizeT
    p.SizeZ = SizeZ
    p.PhysicalSizeX = float(scalex)
    p.PhysicalSizeY = float(scaley)
    p.PhysicalSizeZ = float(scalez if scalez else 0)
    p.PixelType = pixeltype
    p.channel_count = SizeC
    p.plane_count = SizeZ * SizeT * SizeC
    p = writeplanes(p, SizeT=SizeT, SizeZ=SizeZ, SizeC=SizeC, order=dimorder)

    for c in range(SizeC):
        if pixeltype == 'unit8':
            p.Channel(c).SamplesPerPixel = 1
        if pixeltype == 'unit16':
            p.Channel(c).SamplesPerPixel = 2

    omexml.structured_annotations.add_original_metadata(
        ome.OM_SAMPLES_PER_PIXEL, str(SizeC))

    # ome.images[0].description = 'Image 0 description'
    tiffcomment(out_file, omexml.to_xml().encode('utf-8'))

    print('Done writing image.')
    javabridge.kill_vm()
