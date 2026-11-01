import math
import unittest
from datetime import date

import pandas as pd

from core import monthly

TODAY = date(2026, 11, 1)


class MonthsAndYearsTest(unittest.TestCase):
    def test_past_year_shows_all_months(self):
        self.assertEqual(monthly.visible_months(2025, TODAY), list(range(1, 13)))

    def test_current_year_stops_at_last_month(self):
        self.assertEqual(monthly.visible_months(2026, TODAY), list(range(1, 11)))
        self.assertEqual(monthly.visible_months(2026, date(2026, 1, 15)), [])

    def test_future_year_shows_nothing(self):
        self.assertEqual(monthly.visible_months(2027, TODAY), [])

    def test_year_options(self):
        self.assertEqual(monthly.year_options([2023, "2023", None, "x", 2030], TODAY), [2026, 2025, 2023])


class GridTest(unittest.TestCase):
    columns = {"vendor a": "Vendor A", "vendor b": "Vendor B"}
    fixed = {monthly.HOLDER_KEY: "holder x"}
    records = [
        {"holder_key": "holder x", "vendor_key": "vendor a", "year": 2025, "month": 1, "price_per_mt": 150000,
         "density": "1.45"},
        {"holder_key": "holder x", "vendor_key": "vendor b", "year": 2025, "month": 3, "price_per_mt": None,
         "density": 1.5},
        {"holder_key": "holder y", "vendor_key": "vendor a", "year": 2025, "month": 1, "price_per_mt": 999},
        {"holder_key": "holder x", "vendor_key": "vendor a", "year": 2024, "month": 1, "price_per_mt": 888},
    ]

    def grid(self, field):
        return monthly.build_grid(self.records, field, monthly.VENDOR_KEY, self.columns, self.fixed, 2025,
                                  list(range(1, 13)))

    def test_build_grid(self):
        price = self.grid(monthly.FIELD_PRICE)
        self.assertEqual(list(price.columns), ["Vendor A", "Vendor B"])
        self.assertEqual(len(price), 12)
        self.assertEqual(price.at["Jan", "Vendor A"], 150000)
        self.assertTrue(math.isnan(price.at["Mar", "Vendor B"]))
        density = self.grid(monthly.FIELD_DENSITY)
        self.assertAlmostEqual(density.at["Jan", "Vendor A"], 1.45)
        self.assertAlmostEqual(density.at["Mar", "Vendor B"], 1.5)

    def test_changes_only_edited_cells(self):
        before = self.grid(monthly.FIELD_PRICE)
        after = before.copy()
        after.at["Feb", "Vendor B"] = 160000
        after.at["Jan", "Vendor A"] = math.nan   # cleared
        names = {"vendor a": "Vendor A", "vendor b": "Vendor B", "holder x": "Holder X"}
        changes = monthly.grid_changes(before, after, monthly.FIELD_PRICE, monthly.VENDOR_KEY, self.columns,
                                       self.fixed, names, 2025)
        by_month = {(c["vendor_key"], c["month"]): c for c in changes}
        self.assertEqual(len(changes), 2)
        self.assertIsNone(by_month[("vendor a", 1)]["price_per_mt"])
        self.assertEqual(by_month[("vendor b", 2)]["price_per_mt"], 160000)
        self.assertEqual(by_month[("vendor b", 2)]["holder"], "Holder X")
        self.assertEqual(by_month[("vendor b", 2)]["holder_key"], "holder x")
        self.assertNotIn(monthly.FIELD_DENSITY, by_month[("vendor b", 2)])

    def test_averages(self):
        grid = pd.DataFrame({"A": [1.0, 3.0, math.nan], "B": [math.nan] * 3})
        self.assertEqual(monthly.column_averages(grid), {"A": 2.0})


if __name__ == "__main__":
    unittest.main()
