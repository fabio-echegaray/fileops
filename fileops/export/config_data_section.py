import configparser
from pathlib import Path
from typing import Tuple

from roifile import ImagejRoi

from fileops.export._param_override import ParameterOverride
from fileops.export.config_channel_section import update_overrides_from_channel_sections
from fileops.export.config_sections import process_overrides_of_section
from fileops.image import ImageFile
from fileops.image.factory import load_image_file
from fileops.image.ops import PhotoBleachProcessor
from fileops.image.ops.histogram_match_proc import HistogramMatchProcessor
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


def read_data_section(cfg_path, with_root_path: Path | None = None) \
        -> Tuple[configparser.ConfigParser, ImageFile, ParameterOverride, ImagejRoi]:
    cfg = configparser.ConfigParser()
    cfg.read(cfg_path)

    if "DATA" not in cfg:
        raise SyntaxError(f"No header DATA in file {cfg_path}.")

    img_path = Path(cfg["DATA"]["image"])
    if not img_path.is_absolute():
        if with_root_path is not None:
            img_path = with_root_path / img_path
        else:
            img_path = cfg_path.parent / img_path
    if not img_path.exists():
        log.error(f"Image file {img_path} does not exist.")
        raise FileNotFoundError(f"Image file {img_path} does not exist.")

    kwargs = {
        "override_dt": cfg["DATA"]["override_dt"] if "override_dt" in cfg["DATA"] else None,
    }
    if "series" in cfg["DATA"]:
        series_n = int(cfg["DATA"]["series"])
        kwargs.update(dict(image_series=series_n))

    if "use_loader_class" in cfg["DATA"]:
        _cls = _import(f"{cfg['DATA']['use_loader_class']}")
        img_file: ImageFile = _cls(img_path, **kwargs)
    else:
        img_file = load_image_file(img_path, **kwargs)
    if img_file is None:
        raise FileNotFoundError(f"Error loading image file {img_path}.")

    param_override = process_overrides_of_section(cfg["DATA"], ParameterOverride(img_file), img_file)
    param_override = update_overrides_from_channel_sections(param_override, cfg_path)

    img_file.frame_subset = param_override.frames
    img_file.channel_subset = param_override.channels
    img_file.z_subset = param_override.zstacks

    # add image processors
    photobl_corr = False
    if "photobleach_correction" in cfg["DATA"]:
        photobl_corr = cfg["DATA"]["photobleach_correction"]
        img_file.photobleach_correct = photobl_corr if type(photobl_corr) is bool \
            else photobl_corr == "yes" if type(photobl_corr) is str \
            else False
    add_hist_match = False
    if "histogram_matching" in cfg["DATA"]:
        hist_match = cfg["DATA"]["histogram_matching"]
        add_hist_match = hist_match if type(hist_match) is bool \
            else hist_match == "yes" if type(hist_match) is str \
            else False

    # order in which processors are added is the order in which the image is processed
    if photobl_corr:
        print("Adding photobleach correction.")
        pbc = PhotoBleachProcessor()
        img_file.add_processor(pbc)
    if add_hist_match:
        print("Adding histogram matching.")
        ref_fr = param_override.reference_frame if param_override.reference_frame is not None else 0
        hmp = HistogramMatchProcessor(ref_fr)
        img_file.add_processor(hmp)

    # process ROI path. If ROI is defined in DATA section, or in the parameter 'roi' it is used to crop data.
    # Conversely, if it's specified as part of the 'overlay' parameter, it will be plotted.
    roi = None
    if "ROI" in cfg["DATA"]:
        roi_path = Path(cfg["DATA"]["ROI"])
        if not roi_path.is_absolute():
            roi_path = cfg_path.parent / roi_path
            roi = ImagejRoi.fromfile(roi_path)

    return cfg, img_file, param_override, roi
