from copy import deepcopy

import javabridge
import bioformats
import bioformats as bf
import ome_types
from ome_types.model import Channel
import tifffile as tf
from bioformats.formatreader import ImageReader
from javabridge import JavaException
from ome_types.model.pixels import DimensionOrder
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


if __name__ == "__main__":
    javabridge.start_vm(class_path=bioformats.JARS, run_headless=True)
    silence_javabridge_log()

    folder = '/media/lab/Data/Andrew/temp_data/plate_1_real_experiment_1/ome-tif_files/'
    fname = folder + 'plate_1_real_experiment_1_MMStack_0.ome.tif'

    # read image metadata
    o = bf.OMEXML(bf.get_omexml_metadata(path=fname))
    ome = ome_types.from_xml(bf.get_omexml_metadata(path=fname))
    # our weird format would only have one image series; assert this and get image metadata,
    # or throw exception otherwise
    print(f"file has {o.image_count} image series.")
    assert o.image_count == 1, "file has more than one image series."

    im = o.image(index=0)
    print(f"image series has {im.Pixels.SizeC} channels, {im.Pixels.SizeT} frames, "
          f"{im.Pixels.SizeX} px on X dir, {im.Pixels.SizeY} px on Y dir, {im.Pixels.SizeZ} px on Z dir.")
    assert im.Pixels.SizeC == 1 and im.Pixels.SizeZ == 1

    # using modular arithmetic to get the correct images of a particular specimen position
    position = 0
    n_zstacks = 51
    n_positions = 7
    n_channels = 2
    total_frames = 0
    zc = n_zstacks * n_channels
    gap = n_positions * zc

    # initialize image writer
    out_file = f"plate_1_real_experiment_1_MMStack_pos{position}.ome.tiff"
    writer = tf.TiffWriter(out_file, imagej=True, bigtiff=True)

    # iterate through all files and get the images of specific position
    for num in range(1):
        fname = folder + f'plate_1_real_experiment_1_MMStack{"_" + str(num) if num >= 0 else ""}.ome.tif'
        print(f"file {fname}")
        with ImageReader(fname, perform_init=True) as reader:
            # re-read metadata for the specific file
            o = bf.OMEXML(bf.get_omexml_metadata(path=fname))
            im = o.image(index=0)
            for frame in range(im.Pixels.SizeT):
                remaining_frames = im.Pixels.SizeT - frame
                if remaining_frames > gap:
                    print(f"remaining_frames {remaining_frames}")
                    if frame % gap == position:
                        for ix in range(zc):
                            try:
                                print(f"frame {frame + ix} -> {total_frames}")
                                image = reader.read(c=0, z=0, t=frame + ix, rescale=False)
                                writer.save(image, contiguous=True, photometric='minisblack')
                            except JavaException as e:
                                print(e)
                        total_frames += 1

    writer.close()

    # update metadata
    fname = folder + 'plate_1_real_experiment_1_MMStack_0.ome.tif'
    ome = ome_types.from_xml(bf.get_omexml_metadata(path=fname))
    ome.images[0].pixels.dimension_order = DimensionOrder.XYZCT
    ome.images[0].pixels.size_t = total_frames
    ome.images[0].pixels.size_c = n_channels
    ome.images[0].pixels.size_z = n_zstacks
    # ch_2 = deepcopy(ome.images[0].pixels.channels[0])
    # ch_2['id'] = 'Channel:0:1'
    ome.images[0].pixels.channels.append(Channel())
    # ome.images[0].description = 'Image 0 description'
    tiffcomment(out_file, ome.to_xml().encode('utf-8'))

    print('Done writing image.')
    javabridge.kill_vm()
