import unittest

from fileops.export.config_sections import _parse_ranges


class TestParseRanges(unittest.TestCase):

    def test_all_returns_full_range(self):
        result = _parse_ranges("all", 10)
        self.assertEqual(list(result), list(range(10)))

    def test_all_zero_items(self):
        result = _parse_ranges("all", 0)
        self.assertEqual(list(result), [])

    def test_single_int(self):
        result = _parse_ranges("5", 10)
        self.assertEqual(result, [5])

    def test_range_with_dots(self):
        result = _parse_ranges("2..5", 10)
        self.assertEqual(list(result), [2, 3, 4, 5])

    def test_range_from_zero(self):
        result = _parse_ranges("0..3", 10)
        self.assertEqual(list(result), [0, 1, 2, 3])

    def test_list_literal(self):
        result = _parse_ranges("[0, 2, 4]", 10)
        self.assertEqual(result, [0, 2, 4])

    def test_list_literal_unsorted(self):
        result = _parse_ranges("[4, 1, 3]", 10)
        self.assertEqual(result, [1, 3, 4])

    def test_single_element_list(self):
        result = _parse_ranges("[7]", 10)
        self.assertEqual(result, [7])

    def test_invalid_format_raises(self):
        with self.assertRaises((ValueError, IndexError)):
            _parse_ranges("abc", 10)


if __name__ == '__main__':
    unittest.main()
