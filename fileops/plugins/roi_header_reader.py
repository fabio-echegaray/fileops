from pathlib import Path
from typing import List, Dict

from fileops.export._roi import ConfigROI, rectangle_roi_following, parse_static_geometry, rect_params
from fileops.logger import get_logger
from fileops.plugins import HeaderReaderPlugin


class ROIHeaderReaderPlugin(HeaderReaderPlugin):
    log = get_logger(name='ROIHeaderReaderPlugin')

    def has_valid_header(self):
        self._headers = [s for s in self._cfg.sections() if s.upper().startswith("ROI")]
        if len(self._headers) > 0:
            return True
        else:
            self.log.debug(f"No headers of type ROI in file {self._cfg_path}.")
            return False

    def header_output_file_exist(self) -> Dict[str, bool]:
        """ check if output file paths exists without loading the whole structure """
        headers = [s for s in self._cfg.sections() if s.upper().startswith("ROI")]
        if len(headers) == 0:
            self.log.warning(f"No headers with name ROI to check in file {self._cfg_path}.")
            return {"none": False}

        return {h: False for h in headers}

    def process(self) -> List[ConfigROI]:
        if self._headers is None:
            return []

        cfg, param_override, img_file, roi = self._cfg, self._param_override, self._img_file, self._roi

        # process ROI sections
        roi_def = list()
        for roi in self._headers:
            geom = cfg[roi]["geometry"]
            # sec_param_override = process_overrides_of_section(cfg["DATA"], copy.deepcopy(param_override), img_file)
            # sec_param_override = process_overrides_of_section(cfg[roi], sec_param_override, img_file)
            # sec_param_override = update_channel_config_with_section_overrides(sec_param_override, cfg[roi])
            static = "following" not in cfg[roi]
            if "following" in cfg[roi]:
                trj_path = Path(cfg[roi]["following"])
                # trj = pd.read_csv()
                # if len(trj["Track"].unique()) > 1:
                #     raise ValueError(f"More than one track in trajectory file {cfg[roi]['following']}")
            if static:
                geom = parse_static_geometry(geom)
            else:
                name, _, args = geom.partition("(")
                nums = [int(p) for p in args[:-1].split(",")]
                if name == "Square":
                    nums = nums + nums[2:3]  # (x, y, side) -> (x, y, side, side)
                geom = rectangle_roi_following(trj_path, rect_params(*nums))
            roi_def.append(ConfigROI(
                header=roi,
                configfile=self._cfg_path,
                geometry=geom,
            ))
        return roi_def
