import configparser
from pathlib import Path
from typing import Tuple

from roifile import ImagejRoi

from fileops.export._param_override import ParameterOverride
from fileops.export.config_channel_section import update_overrides_from_channel_sections
from fileops.export.config_sections import process_overrides_of_section
from fileops.image import ImageFile
from fileops.image.factory import load_image_file
from fileops.logger import get_logger

log = get_logger(name='export')


# ----------------------------------------------------------------------------------------------------------------------
#  routine that imports a package from a string definition
# ----------------------------------------------------------------------------------------------------------------------
def _import(name):
    components = name.split('.')
    mod = __import__(components[0])
    for comp in components[1:]:
        mod = getattr(mod, comp)
    return mod


def read_data_section(cfg_path) -> Tuple[configparser.ConfigParser, ImageFile, ParameterOverride, ImagejRoi]:
    cfg = configparser.ConfigParser()
    cfg.read(cfg_path)

    assert "DATA" in cfg, f"No header DATA in file {cfg_path}."

    img_path = Path(cfg["DATA"]["image"])
    if not img_path.is_absolute():
        img_path = cfg_path.parent / img_path
    if not img_path.exists():
        log.error(f"Image file {img_path} does not exist.")
        raise FileNotFoundError(f"Image file {img_path} does not exist.")

    kwargs = {
        "override_dt": cfg["DATA"]["override_dt"] if "override_dt" in cfg["DATA"] else None,
    }
    if "series" in cfg["DATA"]:
        series_n = int(cfg["DATA"]["series"])
        kwargs.update(dict(image_series=series_n - 1))

    if "use_loader_class" in cfg["DATA"]:
        _cls = _import(f"{cfg['DATA']['use_loader_class']}")
        img_file: ImageFile = _cls(img_path, **kwargs)
    else:
        img_file = load_image_file(img_path, **kwargs)
    if img_file is None:
        raise FileNotFoundError(f"Error loading image file {img_path}.")

    param_override = process_overrides_of_section(cfg["DATA"], ParameterOverride(img_file), img_file)
    param_override = update_overrides_from_channel_sections(param_override, cfg_path)

    # process ROI path
    roi = None
    if "ROI" in cfg["DATA"]:
        roi_path = Path(cfg["DATA"]["ROI"])
        if not roi_path.is_absolute():
            roi_path = cfg_path.parent / roi_path
            roi = ImagejRoi.fromfile(roi_path)

    return cfg, img_file, param_override, roi
