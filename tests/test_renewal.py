import unittest
from datetime import date, datetime, timedelta

import pandas as pd

from core import renewal
from core.schema import DB_COLS, EXCEL_COLS, RENEWAL_COL, VALID_MANUAL
from core.validation import ValidationSettings, validate_vendors
from core.vendor_status import STATUS_ATTENTION, STATUS_VERIFIED, row_status

NOW = datetime(2026, 10, 30, 9, 0)


def vendor_df(*rows):
    return pd.DataFrame([{**{c: "" for c in DB_COLS}, **row} for row in rows])


class RenewalTrackerTest(unittest.TestCase):
    def test_empty_and_broken_json_give_empty_tracker(self):
        for text in ("", None, "not json", "[1,2]"):
            tracker = renewal.parse(text)
            self.assertTrue(tracker.is_empty)
            self.assertEqual(tracker.total, len(renewal.RENEWAL_STEPS))
        self.assertEqual(renewal.dump(renewal.Renewal()), "")

    def test_only_changed_steps_get_a_timestamp(self):
        first = renewal.update_steps(renewal.Renewal(), [True, False, False, False, False], [""] * 5, NOW)
        self.assertEqual(first.steps[0].updated, "2026-10-30 09:00")
        self.assertEqual(first.steps[1].updated, "")
        later = NOW + timedelta(days=3)
        second = renewal.update_steps(first, [True, True, False, False, False], ["", "sent"], later)
        self.assertEqual(second.steps[0].updated, "2026-10-30 09:00")   # unchanged
        self.assertEqual(second.steps[1].updated, "2026-11-02 09:00")
        self.assertEqual(second.steps[1].note, "sent")
        self.assertEqual(second.done_count, 2)
        self.assertEqual(second.last_update, "2026-11-02 09:00")

    def test_round_trip(self):
        tracker = renewal.mark_verified(
            renewal.update_steps(renewal.Renewal(), [True] * 5, ["a", "", "", "", "SK no. 9"], NOW),
            "2031-10-01", "IUP-NEW", NOW)
        self.assertEqual(renewal.parse(renewal.dump(tracker)), tracker)
        self.assertTrue(tracker.all_done and tracker.is_verified)

    def test_stale_when_no_progress_for_two_weeks(self):
        tracker = renewal.update_steps(renewal.Renewal(), [True, False, False, False, False], [""] * 5, NOW)
        self.assertFalse(renewal.is_stale(tracker, NOW + timedelta(days=13)))
        self.assertTrue(renewal.is_stale(tracker, NOW + timedelta(days=14)))

    def test_latest_tracker_wins_for_a_holder(self):
        old = renewal.dump(renewal.update_steps(renewal.Renewal(), [True] + [False] * 4, [""] * 5, NOW))
        new = renewal.dump(renewal.update_steps(renewal.Renewal(), [True, True] + [False] * 3, [""] * 5,
                                                NOW + timedelta(days=1)))
        df = vendor_df({"iup_nama": "PT Batu Jaya", RENEWAL_COL: old},
                       {"iup_nama": "Batu Jaya", RENEWAL_COL: new},
                       {"iup_nama": "PT Other", RENEWAL_COL: ""})
        trackers = renewal.by_holder(df)
        self.assertEqual(list(trackers), ["batu jaya"])
        self.assertEqual(trackers["batu jaya"].done_count, 2)


class CompletedRenewalValidationTest(unittest.TestCase):
    def setUp(self):
        self.soon = (date.today() + timedelta(days=30)).isoformat()
        self.renewed = (date.today() + timedelta(days=5 * 365)).isoformat()
        self.minerba = pd.DataFrame({"nama_badan_usaha": ["PT Batu Jaya"], "tanggal_berakhir": [self.soon]})
        self.cfg = ValidationSettings(match_col="nama_badan_usaha",
                                      field_map={"iup_tanggal_berakhir": "tanggal_berakhir"})

    def _tracker(self, verified: bool) -> str:
        tracker = renewal.update_steps(renewal.Renewal(), [True] * 5, [""] * 5, NOW)
        if verified:
            tracker = renewal.mark_verified(tracker, self.renewed, "IUP-NEW", NOW)
        return renewal.dump(tracker)

    def test_expiring_holder_stays_amber_until_verified(self):
        df = vendor_df({"vendor": "A", "iup_nama": "PT Batu Jaya", RENEWAL_COL: self._tracker(verified=False)})
        out = validate_vendors(df, self.minerba, self.cfg)
        self.assertEqual(row_status(out).iloc[0], STATUS_ATTENTION)

    def test_verified_renewal_beats_old_minerbaone_date_for_every_row_of_the_holder(self):
        df = vendor_df(
            {"vendor": "A", "iup_nama": "PT Batu Jaya", RENEWAL_COL: self._tracker(verified=True)},
            {"vendor": "B", "iup_nama": "Batu Jaya", RENEWAL_COL: ""},   # same holder, other vendor
        )
        out = validate_vendors(df, self.minerba, self.cfg)
        self.assertEqual(list(out["iup_tanggal_berakhir"]), [self.renewed, self.renewed])
        self.assertEqual(list(out["iup_nomor"]), ["IUP-NEW", "IUP-NEW"])
        self.assertEqual(list(row_status(out)), [STATUS_VERIFIED, STATUS_VERIFIED])
        self.assertEqual(list(out["minerbaone"]), ["Valid", "Valid"])

    def test_verified_holder_missing_from_minerbaone_counts_as_manual_valid(self):
        df = vendor_df({"vendor": "A", "iup_nama": "PT Unknown", "iup_tanggal_berakhir": self.soon,
                        RENEWAL_COL: self._tracker(verified=True)})
        out = validate_vendors(df, self.minerba, self.cfg)
        self.assertEqual(out["minerbaone"].iloc[0], VALID_MANUAL)
        self.assertEqual(row_status(out).iloc[0], STATUS_VERIFIED)

    def test_tracker_column_is_not_exported_to_excel(self):
        self.assertNotIn(RENEWAL_COL, EXCEL_COLS)
        self.assertIn("lokasi_maps", EXCEL_COLS)


if __name__ == "__main__":
    unittest.main()


class RemarkStepsTest(unittest.TestCase):
    def test_steps_read_from_remark(self):
        text = "1. Prepare renewal documents; updated on 2026-01-10 | 3. Document review; updated on 2026-02-01"
        tracker = renewal.from_remark(text)
        self.assertEqual(tracker.done_count, 2)
        self.assertTrue(tracker.steps[0].done)
        self.assertEqual(tracker.steps[0].note, "")                 # standard title -> no note
        self.assertEqual(tracker.steps[2].note, "Document review")  # custom text kept as note
        self.assertEqual(tracker.last_update, "2026-02-01 00:00")

    def test_multiline_and_noise(self):
        text = "IUP being renewed\n2. Submitted; updated 2026-03-05\n9. Unknown; updated on 2026-03-06\nphone 0812.3"
        tracker = renewal.from_remark(text)
        self.assertEqual([s.done for s in tracker.steps], [False, True, False, False, False])

    def test_no_steps_gives_empty_tracker(self):
        for text in ("", None, "just a note", "1. step without date"):
            self.assertTrue(renewal.from_remark(text).is_empty)

    def test_saved_tracker_wins_over_remark(self):
        saved = renewal.dump(renewal.update_steps(renewal.Renewal(), [True] + [False] * 4, [""] * 5, NOW))
        tracker, from_remark = renewal.for_rows([saved], ["2. X; updated on 2026-01-01"])
        self.assertFalse(from_remark)
        self.assertTrue(tracker.steps[0].done)
        tracker, from_remark = renewal.for_rows(["", None], ["", "2. X; updated on 2026-01-01"])
        self.assertTrue(from_remark)
        self.assertTrue(tracker.steps[1].done)
