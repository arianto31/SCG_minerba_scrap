import unittest

import pandas as pd

from core.phone import to_whatsapp_url, with_whatsapp_links


class PhoneTest(unittest.TestCase):
    def test_indonesian_formats_become_wa_links(self):
        expected = "https://wa.me/6281234567890"
        for raw in ("0812-3456-7890", "+62 812 3456 7890", "6281234567890", "81234567890",
                    "0062 812 3456 7890", "620812 3456 7890", " (0812) 3456 7890 "):
            self.assertEqual(to_whatsapp_url(raw), expected, raw)

    def test_first_number_is_used_when_many(self):
        self.assertEqual(to_whatsapp_url("0812 3456 7890 / 0813 1111 2222"), "https://wa.me/6281234567890")
        self.assertEqual(to_whatsapp_url("0812 3456 7890, 0813 1111 2222"), "https://wa.me/6281234567890")

    def test_invalid_or_blank_returns_none(self):
        for raw in (None, "", "-", "Pak Budi", "123", float("nan")):
            self.assertIsNone(to_whatsapp_url(raw), raw)

    def test_with_whatsapp_links_keeps_original_frame(self):
        df = pd.DataFrame({"no_kontak": ["0812 3456 7890", "-"], "vendor": ["A", "B"]})
        shown = with_whatsapp_links(df)
        self.assertEqual(shown.loc[0, "no_kontak"], "https://wa.me/6281234567890")
        self.assertIsNone(shown.loc[1, "no_kontak"])
        self.assertEqual(df.loc[0, "no_kontak"], "0812 3456 7890")  # aslinya tidak berubah


if __name__ == "__main__":
    unittest.main()
