import configparser
from pathlib import Path
from typing import Tuple

import numpy as np
from roifile import ImagejRoi

from fileops.export._param_override import ParameterOverride
from fileops.export._roi import parse_static_geometry
from fileops.export.config_channel_section import update_overrides_from_channel_sections
from fileops.export.config_sections import process_overrides_of_section, read_defaults_into_cfg, read_cfg_into
from fileops.image import ImageFile
from fileops.image.factory import load_image_file
from fileops.image.ops import PhotoBleachProcessor
from fileops.image.ops.histogram_match_proc import HistogramMatchProcessor
from fileops.image.ops.rescale_proc import RescaleProcessor
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


def parse_pixel_size(spec) -> float | None:
    """Parse a pixel-size override from a cfg ``[DATA] pixel_size`` value.

    Returns micrometres per pixel, or None when the spec cannot be used.
    Accepted forms (number + optional unit; default unit is um):
      ``0.107``, ``0.107 um``, ``0.107 µm``, ``107 nm``,
      ``1.07e-4 mm``, ``1.07e-7 m``
    """
    if not isinstance(spec, str):
        return None
    parts = spec.strip().split()
    try:
        value = float(parts[0])
    except (IndexError, ValueError):
        return None
    if value <= 0:
        return None
    unit = parts[1].lower() if len(parts) > 1 else 'um'
    if unit in ('um', 'µm', 'micron', 'microns'):
        return value
    if unit == 'nm':
        return value * 1e-3
    if unit == 'mm':
        return value * 1e3
    if unit == 'm':
        return value * 1e6
    return None


def resolve_media_path(cfg_path, with_root_path: Path | None, img_path: Path) -> Path:
    """Resolve the media file path stored in a configuration file.

    * Relative stored paths resolve against *with_root_path* when one is
      given, otherwise against the configuration file folder.
    * Absolute stored paths are honoured as-is when they exist.
    * An absolute stored path that does not exist (e.g. it still points at
      the mount root of the machine where the file was written, like
      ``/Volumes/...`` on macOS) is re-anchored under *with_root_path*: the
      most specific existing tail of the stored path is used, progressively
      dropping the volume-specific leading folders. This lets a path like
      ``/Volumes/T7/Microscope/Nikon (CPF)/2024.../data.ome.tif`` be found
      at ``<root>/Nikon (CPF)/2024.../data.ome.tif`` once the mount-specific
      prefix is gone.
    """
    if img_path.is_absolute():
        if img_path.exists():
            return img_path
        if with_root_path is not None:
            try:
                parts = img_path.relative_to(img_path.anchor).parts
            except ValueError:
                return img_path
            for ix in range(len(parts)):
                candidate = with_root_path.joinpath(*parts[ix:])
                if candidate.exists():
                    log.debug(f"Re-anchored media path {img_path} under "
                              f"root path {with_root_path} -> {candidate}")
                    return candidate
        return img_path
    if with_root_path is not None:
        return with_root_path / img_path
    return cfg_path.parent / img_path


def read_data_section(cfg_path, with_root_path: Path | None = None,
                      defaults_file: Path | list[Path] | None = None) \
        -> Tuple[configparser.ConfigParser, ImageFile, ParameterOverride, ImagejRoi]:
    cfg = configparser.ConfigParser()
    if defaults_file is not None:
        read_defaults_into_cfg(cfg, defaults_file)
    read_cfg_into(cfg, cfg_path)

    if "DATA" not in cfg:
        raise SyntaxError(f"No header DATA in file {cfg_path}.")

    img_path = resolve_media_path(cfg_path, with_root_path, Path(cfg["DATA"]["image"]))
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

    # look for a calibration override in cfg file
    if "pixel_size" in cfg["DATA"]:
        um_per_pix = parse_pixel_size(cfg["DATA"]["pixel_size"])
        if um_per_pix is not None and um_per_pix > 0:
            img_file.um_per_pix = um_per_pix
            img_file.pix_per_um = 1.0 / um_per_pix
            log.debug(f"pixel_size override from cfg: "
                      f"{um_per_pix:.6g} um/pix -> {img_file.pix_per_um:.4f} pix/um")
        else:
            log.warning(f"ignoring invalid pixel_size override: "
                        f"{cfg['DATA']['pixel_size']!r} (expected e.g. '0.107 um' or '107 nm')")

    param_override = process_overrides_of_section(cfg["DATA"], ParameterOverride(img_file), img_file)
    param_override = update_overrides_from_channel_sections(param_override, cfg_path, defaults_file=defaults_file)

    img_file.frame_subset = param_override.frames
    img_file.channel_subset = param_override.channels
    img_file.z_subset = param_override.zstacks

    # add image processors
    photobl_corr = False
    if "photobleach_correction" in cfg["DATA"]:
        photobl_corr = cfg["DATA"]["photobleach_correction"]
        photobl_corr = photobl_corr if type(photobl_corr) is bool \
            else photobl_corr == "yes" if type(photobl_corr) is str \
            else False
    add_hist_match = False
    if "histogram_matching" in cfg["DATA"]:
        hist_match = cfg["DATA"]["histogram_matching"]
        add_hist_match = hist_match if type(hist_match) is bool \
            else hist_match == "yes" if type(hist_match) is str \
            else False
    rescale_op = False
    if "rescale" in cfg["DATA"]:
        rescale_op = cfg["DATA"]["rescale"]
        rescale_op = rescale_op if type(rescale_op) is bool \
            else rescale_op == "yes" if type(rescale_op) is str \
            else False
    # rescale parameters can also live in CHANNEL sections, so we should also check in those!
    # (an explicit `rescale = yes/no` in [DATA] takes precedence over any of them)
    elif np.any(["rescale_min" in cfg[s] or "rescale_max" in cfg[s] for s in cfg.sections()]):
        rescale_op = True

    # order in which processors are added is the order in which the image is processed
    if photobl_corr:
        print("Adding photobleach correction.")
        pbc = PhotoBleachProcessor()
        img_file.add_processor(pbc)
    if rescale_op:
        print("Adding intensity rescaling correction.")
        rop = RescaleProcessor(param_override.channel_info)
        img_file.add_processor(rop)
    if add_hist_match:
        print("Adding histogram matching.")
        ref_fr = param_override.reference_frame if param_override.reference_frame is not None else 0
        hmp = HistogramMatchProcessor(ref_fr)
        img_file.add_processor(hmp)

    # process ROI path. If ROI is defined in DATA section, or in the parameter 'roi' it is used to crop data.
    # Conversely, if it's specified as part of the 'overlay' parameter, it will be plotted.
    roi = None
    if "ROI" in cfg["DATA"]:
        roi_ref = cfg["DATA"]["ROI"]
        roi_path = Path(roi_ref)
        if not roi_path.is_absolute():
            roi_path = cfg_path.parent / roi_path
        if roi_path.exists():
            roi = ImagejRoi.fromfile(roi_path)
        else:
            roi = _roi_from_config_sections(cfg, roi_ref, pix_per_um=img_file.pix_per_um)
            if roi is None:
                raise FileNotFoundError(
                    f"ROI {roi_ref!r} set in [DATA] is neither an existing file "
                    f"({roi_path}) nor a [ROI-xx] section with that id/header.")

    return cfg, img_file, param_override, roi


def _roi_from_config_sections(cfg, roi_ref, pix_per_um: float | None = None) -> ImagejRoi | None:
    """Resolve a ``[DATA] roi = <ref>`` value against the config's ROI sections.

    The reference matches either a ROI section *header* (e.g. ``[roi_001]``)
    or its ``id`` key (e.g. ``[ROI-01]`` with ``id = roi_001``), case-
    insensitively. The matched section's ``geometry`` is parsed into an
    ImagejRoi; ``pix_per_um`` enables metric-unit geometries. Returns None
    when no section matches."""
    roi_ref = roi_ref.lower()
    for sec in cfg.sections():
        if not sec.upper().startswith("ROI"):
            continue
        if cfg[sec].get("id", sec).lower() != roi_ref and sec.lower() != roi_ref:
            continue
        if "geometry" not in cfg[sec]:
            raise ValueError(f"ROI section {sec} matching {roi_ref!r} has no 'geometry'.")
        log.debug(f"Using ROI section {sec} (id {cfg[sec].get('id', sec)}) to crop.")
        return parse_static_geometry(cfg[sec]["geometry"], pix_per_um=pix_per_um)
    return None
