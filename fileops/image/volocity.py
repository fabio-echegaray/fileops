from fileops.image import OMEImageFile
from fileops.logger import get_logger


class VolocityFile(OMEImageFile):
    log = get_logger(name='VolocityFile')
