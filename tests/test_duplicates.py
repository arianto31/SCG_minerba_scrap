import unittest

import pandas as pd

from core import duplicates
from core.schema import DB_COLS


def vendor_df(*rows):
    df = pd.DataFrame([{**{c: "" for c in DB_COLS}, **row} for row in rows])
    df.index = df.index + 1
    return df


class DuplicatesTest(unittest.TestCase):
    def setUp(self):
        self.saved = vendor_df(
            {"vendor": "CV Abadi Jaya", "iup_nama": "PT Batu Alam Sejahtera"},
            {"vendor": "PT Sumber Pasir", "iup_nama": "PT Pasir Makmur"},
            {"vendor": "UD Lain", "iup_nama": "PT Gunung Kapur"},
        )

    def test_same_name_ignores_legal_form_case_and_punctuation(self):
        found = duplicates.find_related(self.saved, holder="batu alam sejahtera, pt")
        self.assertEqual(list(found.index), [1])
        self.assertEqual(found[duplicates.MATCH_COLUMN].iloc[0], "Same IUP holder")

    def test_similar_vendor_is_listed(self):
        found = duplicates.find_related(self.saved, vendor="Abadi Jaya Group")
        self.assertEqual(list(found.index), [1])
        self.assertEqual(found[duplicates.MATCH_COLUMN].iloc[0], "Similar vendor")

    def test_unrelated_name_finds_nothing(self):
        self.assertTrue(duplicates.find_related(self.saved, vendor="Zeta", holder="PT Omega").empty)
        self.assertTrue(duplicates.find_related(self.saved).empty)

    def test_editor_only_checks_new_rows(self):
        edited = pd.concat([self.saved, vendor_df({"vendor": "Sumber Pasir", "iup_nama": "PT Baru"})],
                           ignore_index=True)
        related = duplicates.related_to_new_rows(edited, self.saved)
        self.assertEqual(list(related.index), [2])
        self.assertTrue(duplicates.related_to_new_rows(self.saved, self.saved).empty)


if __name__ == "__main__":
    unittest.main()
