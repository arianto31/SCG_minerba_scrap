import unittest

import pandas as pd

from core import material_groups as mg


class MaterialGroupsTest(unittest.TestCase):
    def test_base_first_then_others_without_duplicates(self):
        options = mg.build_options(["pasir", " Split ", "", None, "BATUAN"], ["split", "Abu Batu"])
        self.assertEqual(options, ["Batuan", "Pasir", "Fly Ash", "Abu Batu", "Split"])

    def test_canonical_spelling(self):
        options = ["Batuan", "Pasir", "Fly Ash", "Split"]
        self.assertEqual(mg.canonical("  fly   ash ", options), "Fly Ash")
        self.assertEqual(mg.canonical("SPLIT", options), "Split")
        self.assertEqual(mg.canonical("Kerikil", options), "Kerikil")   # new group kept as typed
        self.assertEqual(mg.canonical(None, options), "")

    def test_canonical_column(self):
        out = mg.canonical_column(pd.Series(["batuan", "", "pasir "]), mg.BASE_GROUPS)
        self.assertEqual(list(out), ["Batuan", "", "Pasir"])


if __name__ == "__main__":
    unittest.main()
