import unittest

import pandas as pd

from core.schema import AUTO_TAG, DB_COLS, pretty_label
from core.vendor_status import (
    STATUS_ATTENTION, STATUS_INCOMPLETE, STATUS_NOT_FOUND, STATUS_VERIFIED, row_status, summarize,
)


def vendor_df(*rows):
    return pd.DataFrame([{**{c: "" for c in DB_COLS}, **row} for row in rows])


class VendorStatusTest(unittest.TestCase):
    def setUp(self):
        self.df = vendor_df(
            {"iup_nama": "PT A", "minerbaone": "Valid"},                                       # verified
            {"iup_nama": "PT B", "minerbaone": "-"},                                           # not found
            {"iup_nama": "PT C", "minerbaone": "Valid", "remark": f"{AUTO_TAG} IUP expires in 9 days"},
            {"iup_nama": "PT D", "minerbaone": "-", "remark": "[PERINGATAN] IUP sudah berakhir"},  # legacy tag
            {"vendor": "No IUP yet", "minerbaone": "-"},                                       # incomplete
        )

    def test_row_status_priority_matches_row_colors(self):
        self.assertEqual(list(row_status(self.df)), [
            STATUS_VERIFIED, STATUS_NOT_FOUND, STATUS_ATTENTION, STATUS_NOT_FOUND, STATUS_INCOMPLETE,
        ])

    def test_summary_counts(self):
        s = summarize(self.df)
        self.assertEqual((s.total, s.verified, s.not_found, s.attention), (4, 2, 2, 2))

    def test_rows_without_iup_name_are_not_counted_as_not_found(self):
        self.assertEqual(summarize(vendor_df({"vendor": "X", "minerbaone": "-"})).not_found, 0)

    def test_empty_frame(self):
        self.assertEqual(summarize(pd.DataFrame(columns=DB_COLS)).total, 0)

    def test_every_column_has_an_english_label(self):
        for column in DB_COLS:
            self.assertTrue(pretty_label(column))
        self.assertEqual(pretty_label("iup_tanggal_terbit"), "IUP · Issue Date")


if __name__ == "__main__":
    unittest.main()
