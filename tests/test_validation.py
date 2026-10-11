import unittest
from datetime import date, timedelta

import pandas as pd

from core.schema import AUTO_TAG, DB_COLS
from core.validation import ValidationSettings, default_field_map, validate_vendors


def vendor_df(*rows):
    df = pd.DataFrame([{**{c: "" for c in DB_COLS}, **row} for row in rows])
    df.index = df.index + 1
    return df


class ValidationTest(unittest.TestCase):
    def setUp(self):
        self.end = (date.today() + timedelta(days=30)).strftime("%Y-%m-%d")
        self.minerba = pd.DataFrame({
            "nama_badan_usaha": ["PT SUMBER GUNUNG MAJU", "CV CENTRAL ADI PERKASA"],
            "tanggal_berlaku_awal": ["2023-04-18", "2024-06-13"],
            "tanggal_berlaku_akhir": [self.end, "2029-06-12"],
        })
        self.cfg = ValidationSettings(
            threshold=100, warn_days=180, match_col="nama_badan_usaha",
            field_map=default_field_map(list(self.minerba.columns)),
        )

    def test_default_field_map_detects_dates(self):
        self.assertEqual(self.cfg.field_map["iup_tanggal_terbit"], "tanggal_berlaku_awal")
        self.assertEqual(self.cfg.field_map["iup_tanggal_berakhir"], "tanggal_berlaku_akhir")

    def test_match_fills_columns_and_warns(self):
        df = vendor_df({"iup_nama": "pt. sumber gunung maju"}, {"iup_nama": "PT TIDAK ADA"})
        out = validate_vendors(df, self.minerba, self.cfg)
        self.assertEqual(out.loc[1, "minerbaone"], "Valid")
        self.assertEqual(out.loc[1, "iup_tanggal_terbit"], "2023-04-18")
        self.assertEqual(out.loc[1, "iup_countdown"], "30")
        self.assertIn(AUTO_TAG, out.loc[1, "remark"])
        self.assertEqual(out.loc[2, "minerbaone"], "-")

    def test_manual_remark_is_kept_and_old_warning_replaced(self):
        df = vendor_df({"iup_nama": "PT SUMBER GUNUNG MAJU", "remark": f"{AUTO_TAG} lama | catatan saya"})
        remark = validate_vendors(df, self.minerba, self.cfg).loc[1, "remark"]
        self.assertIn("catatan saya", remark)
        self.assertNotIn("lama", remark)

    def test_fuzzy_threshold(self):
        df = vendor_df({"iup_nama": "PT SUMBER GUNUNG MAJUU"})
        strict = validate_vendors(df, self.minerba, self.cfg)
        loose = validate_vendors(df, self.minerba, ValidationSettings(
            threshold=80, match_col="nama_badan_usaha", field_map=self.cfg.field_map))
        self.assertEqual(strict.loc[1, "minerbaone"], "-")
        self.assertEqual(loose.loc[1, "minerbaone"], "Valid")

    def test_empty_minerba_marks_all_invalid(self):
        out = validate_vendors(vendor_df({"iup_nama": "X"}), pd.DataFrame(), self.cfg)
        self.assertEqual(out.loc[1, "minerbaone"], "-")


if __name__ == "__main__":
    unittest.main()
