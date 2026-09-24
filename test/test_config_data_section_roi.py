import configparser

import pytest
from roifile import ImagejRoi

from fileops.export._roi import parse_static_geometry
from fileops.export.config_data_section import _roi_from_config_sections


class TestParseStaticGeometry:
    def test_square(self):
        roi = parse_static_geometry("Square(20,30,50)")
        assert isinstance(roi, ImagejRoi)
        # roifile reports right/bottom as exclusive edges (+1)
        assert (roi.left, roi.top, roi.right, roi.bottom) == (-5, 5, 46, 56)

    def test_rectangle(self):
        roi = parse_static_geometry("Rectangle(10,20,40,60)")
        assert (roi.left, roi.top, roi.right, roi.bottom) == (-10, -10, 31, 51)

    def test_rectangle_metric_um(self):
        roi = parse_static_geometry("Rectangle(10um,20um,40um,60um)", pix_per_um=9.35)
        # x = 93.5 px, y = 187.0 px, w = 374.0 px, h = 561.0 px
        # centered -> x0 = 93.5-187 = -93.5 -> int -> -93 ; right = -93+374 = 281 (+1)
        assert (roi.left, roi.top, roi.right, roi.bottom) == (-93, -93, 281, 468)

    def test_rectangle_metric_um_float(self):
        roi = parse_static_geometry("Rectangle(10.3um,20.1um,40.45um,60.324um)", pix_per_um=9.35)
        # x = 96.305, y = 187.935, w = 378.2075, h = 564.0294 px
        # x0 = 96.305 - 189.10375 = -92.79... -> int -> -92
        # y0 = 187.935 - 282.0147  = -94.07... -> int -> -94
        # x1 = 96.305 + 189.10375 = 285.40... -> int -> 285 (+1 -> 286)
        # y1 = 187.935 + 282.0147 = 469.94... -> int -> 469 (+1 -> 470)
        assert (roi.left, roi.top, roi.right, roi.bottom) == (-92, -94, 286, 470)

    def test_rectangle_metric_mixed_units(self):
        # um, nm, mm are all converted via the same pix_per_um scale
        roi = parse_static_geometry("Rectangle(1mm,2000um,100um,100000nm)", pix_per_um=10)
        # x = 10000 px, y = 20000 px, w = 1000 px, h = 1000 px
        assert (roi.left, roi.top, roi.right, roi.bottom) == (9500, 19500, 10501, 20501)

    def test_rectangle_metric_requires_calibration(self):
        with pytest.raises(ValueError, match="no pixel-size calibration"):
            parse_static_geometry("Rectangle(10um,20um,40um,60um)")

    def test_unsupported_shape(self):
        with pytest.raises(ValueError):
            parse_static_geometry("Circle(10,20,30)")

    def test_bad_number_of_args(self):
        with pytest.raises(ValueError):
            parse_static_geometry("Square(10,20)")

    def test_bad_unit(self):
        with pytest.raises(ValueError, match="Unsupported ROI geometry unit"):
            parse_static_geometry("Rectangle(10ft,20,40,60)", pix_per_um=1)


class TestRoiFromConfigSections:
    def _cfg(self, text):
        cfg = configparser.ConfigParser()
        cfg.read_string(text)
        return cfg

    def test_match_by_id(self):
        cfg = self._cfg(
            "[ROI-01]\n"
            "id = roi_001\n"
            "geometry = Square(20,30,50)\n"
        )
        roi = _roi_from_config_sections(cfg, "roi_001")
        assert isinstance(roi, ImagejRoi)
        assert (roi.left, roi.top, roi.right, roi.bottom) == (-5, 5, 46, 56)

    def test_match_by_id_metric(self):
        cfg = self._cfg(
            "[ROI-01]\n"
            "id = roi_um\n"
            "geometry = Rectangle(10um,20um,40um,60um)\n"
        )
        roi = _roi_from_config_sections(cfg, "roi_um", pix_per_um=9.35)
        assert (roi.left, roi.top, roi.right, roi.bottom) == (-93, -93, 281, 468)

    def test_match_by_header_case_insensitive(self):
        cfg = self._cfg(
            "[roi_001]\n"
            "geometry = Square(0,0,10)\n"
        )
        roi = _roi_from_config_sections(cfg, "ROI_001")
        assert isinstance(roi, ImagejRoi)

    def test_no_match_returns_none(self):
        cfg = self._cfg(
            "[ROI-01]\n"
            "id = roi_other\n"
            "geometry = Square(0,0,10)\n"
        )
        assert _roi_from_config_sections(cfg, "roi_001") is None

    def test_matching_section_without_geometry_raises(self):
        cfg = self._cfg(
            "[ROI-01]\n"
            "id = roi_001\n"
        )
        with pytest.raises(ValueError):
            _roi_from_config_sections(cfg, "roi_001")