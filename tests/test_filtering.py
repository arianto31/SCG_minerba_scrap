import unittest

import pandas as pd

from core.filtering import filter_dataframe


class FilteringTest(unittest.TestCase):
    def setUp(self):
        self.df = pd.DataFrame({
            "nama_badan_usaha": ["PT Sumber Gunung Maju", "CV Central Adi Perkasa", "PT (Persero) Aneka"],
            "komoditas": ["Andesit", "Pasir", "Batu Kapur"],
            "status": ["Aktif", "AKTIF", "Mati"],
        })

    def test_column_filter_ignores_case(self):
        out = filter_dataframe(self.df, column_queries={"nama_badan_usaha": "sUmBeR gunung"})
        self.assertEqual(list(out["komoditas"]), ["Andesit"])

    def test_multiple_column_filters_are_and(self):
        out = filter_dataframe(self.df, column_queries={"status": "aktif", "komoditas": "PASIR"})
        self.assertEqual(list(out["nama_badan_usaha"]), ["CV Central Adi Perkasa"])

    def test_substring_match_anywhere(self):
        self.assertEqual(len(filter_dataframe(self.df, column_queries={"komoditas": "atu"})), 1)

    def test_special_characters_are_literal(self):
        out = filter_dataframe(self.df, column_queries={"nama_badan_usaha": "(persero)"})
        self.assertEqual(len(out), 1)

    def test_global_query_searches_all_columns(self):
        self.assertEqual(len(filter_dataframe(self.df, query="PASIR")), 1)
        self.assertEqual(len(filter_dataframe(self.df, query="aktif")), 2)

    def test_global_and_column_filters_combine(self):
        out = filter_dataframe(self.df, query="aktif", column_queries={"komoditas": "andesit"})
        self.assertEqual(len(out), 1)

    def test_empty_filters_return_everything(self):
        self.assertEqual(len(filter_dataframe(self.df, "", {"status": "  ", "komoditas": ""})), 3)
        self.assertEqual(len(filter_dataframe(self.df.iloc[0:0], query="x")), 0)


if __name__ == "__main__":
    unittest.main()
