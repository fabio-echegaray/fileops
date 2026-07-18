import pytest

from fileops.export.config_sections import _parse_ranges


class TestParseRanges:
    def test_all_returns_full_range(self):
        result = _parse_ranges("all", 10)
        assert list(result) == list(range(10))

    def test_all_zero_items(self):
        result = _parse_ranges("all", 0)
        assert list(result) == []

    def test_single_int(self):
        result = _parse_ranges("5", 10)
        assert result == [5]

    def test_range_with_dots(self):
        result = _parse_ranges("2..5", 10)
        assert list(result) == [2, 3, 4, 5]

    def test_range_from_zero(self):
        result = _parse_ranges("0..3", 10)
        assert list(result) == [0, 1, 2, 3]

    def test_list_literal(self):
        result = _parse_ranges("[0, 2, 4]", 10)
        assert result == [0, 2, 4]

    def test_list_literal_unsorted(self):
        result = _parse_ranges("[4, 1, 3]", 10)
        assert result == [1, 3, 4]

    def test_single_element_list(self):
        result = _parse_ranges("[7]", 10)
        assert result == [7]

    def test_invalid_format_raises(self):
        with pytest.raises((ValueError, IndexError)):
            _parse_ranges("abc", 10)
