import unittest

import pandas as pd

from core import required
from core.schema import DB_COLS


def df(*rows):
    out = pd.DataFrame([{**{c: "" for c in DB_COLS}, **r} for r in rows])
    out.index = out.index + 1
    return out


FULL = {"iup_nama": "PT Batu", "vendor": "CV Maju", "nama_pic": "Budi", "golongan": "Batuan"}


class RequiredFieldsTest(unittest.TestCase):
    def test_missing_fields(self):
        self.assertEqual(required.missing_fields(FULL), [])
        self.assertEqual(required.missing_fields({**FULL, "nama_pic": " ", "golongan": None}),
                         ["PIC Name", "Material Group"])

    def test_incomplete_rows_skip_empty_rows(self):
        rows = df(FULL, {"vendor": "CV Only"}, {}, {"nib_nomor": "123"})
        incomplete = required.incomplete_rows(rows)
        self.assertEqual(list(incomplete.index), [2, 4])   # empty row 3 is ignored
        self.assertEqual(incomplete.at[2, required.MISSING_COLUMN], "Holder Name, PIC Name, Material Group")

    def test_new_rows_ignore_edits_of_existing_records(self):
        saved = df({"iup_nama": "PT Lama", "vendor": "CV Lama"})                     # legacy, incomplete
        edited = df({"iup_nama": "PT Lama", "vendor": "CV Lama", "no_kontak": "0812"},  # only phone edited
                    {"vendor": "CV Baru"})                                          # new row
        new = required.new_rows(edited, saved)
        self.assertEqual(list(new["vendor"]), ["CV Baru"])
        self.assertEqual(len(required.incomplete_rows(new)), 1)

    def test_required_text(self):
        self.assertEqual(required.required_text(), "Holder Name, Vendor, PIC Name and Material Group")


if __name__ == "__main__":
    unittest.main()
