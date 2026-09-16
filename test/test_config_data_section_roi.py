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

    def test_unsupported_shape(self):
        with pytest.raises(ValueError):
            parse_static_geometry("Circle(10,20,30)")

    def test_bad_number_of_args(self):
        with pytest.raises(ValueError):
            parse_static_geometry("Square(10,20)")


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