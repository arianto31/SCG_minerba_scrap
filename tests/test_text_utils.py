import unittest
from datetime import datetime

import pandas as pd

from core.text_utils import clean_key, is_blank, normalize_name, parse_date, to_int_str, to_iso_date


class TextUtilsTest(unittest.TestCase):
    def test_normalize_name_ignores_legal_entity_and_punctuation(self):
        self.assertEqual(normalize_name("PT. Maju  Jaya"), normalize_name("maju jaya"))
        self.assertEqual(normalize_name(None), "")

    def test_is_blank(self):
        for value in (None, "", " - ", "nan", float("nan")):
            self.assertTrue(is_blank(value), value)
        self.assertFalse(is_blank("abc"))
        self.assertFalse(is_blank(datetime(2024, 1, 1)))

    def test_parse_date_formats(self):
        self.assertEqual(parse_date("2026-10-18"), pd.Timestamp(2026, 10, 18))
        self.assertEqual(parse_date("30/01/2019"), pd.Timestamp(2019, 1, 30))
        self.assertEqual(parse_date("1 Maret 2025"), pd.Timestamp(2025, 3, 1))
        self.assertTrue(pd.isna(parse_date("-")))

    def test_to_iso_date_keeps_unparseable_text(self):
        self.assertEqual(to_iso_date("30/01/2019"), "2019-01-30")
        self.assertEqual(to_iso_date("bukan tanggal"), "bukan tanggal")

    def test_to_int_str(self):
        self.assertEqual(to_int_str("5.116"), "5")
        self.assertEqual(to_int_str("5,6"), "6")
        self.assertEqual(to_int_str("abc"), "abc")

    def test_clean_key_drops_parentheses(self):
        self.assertEqual(clean_key("NIB (NOMOR INDUK BERUSAHA)"), "nib")
