import os.path

import numpy as np
import javabridge
from tifffile import imsave

from cached import CachedImageFile
from cached.image_file import ensure_dir
from logger import get_logger

log = get_logger(name='__main__')

if __name__ == "__main__":
    # open file and select timeseries
    path = r"C:\Data\Anand\Sas6-GFP_Sqh-mCherry_bisect_05_20_2021\Sas6-GFP_Sqh-mCherry_bisect_05_20_2021.mvd2"

    img_struct = CachedImageFile(path, image_series=0, cache_results=False)

    log.info("Exporting series of volumes.")
    base_dir = os.path.dirname(path)
    sav_path = os.path.join(base_dir, '_vol_paraview')
    ensure_dir(os.path.join(sav_path, 'dummy'))

    image = np.empty(shape=(len(img_struct.zstacks), img_struct.width, img_struct.height), dtype=np.uint16)
    for j, c in enumerate(img_struct.channels):
        for fr in img_struct.frames:
            for i, z in enumerate(img_struct.zstacks):
                ix = img_struct.ix_at(c=j, z=z, t=fr)
                mdimg = img_struct.image(ix)
                image[i, :, :] = mdimg.image
            fname = f'C{c:02d}T{fr:04d}_vol.tiff'
            fpath = os.path.join(sav_path, fname)
            log.debug(f"Saving image {fname} in cache (path={fpath}).")
            imsave(fpath, np.array(image), imagej=True, metadata={'order': 'ZXY'})

    # --------------------------------------
    #  Finish
    # --------------------------------------
    javabridge.kill_vm()
