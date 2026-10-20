import json
import unittest
from types import SimpleNamespace

from core.schema import DB_COLS
from services.document_ai import (
    FILLABLE_COLUMNS,
    ExtractedDocument,
    ExtractionError,
    GeminiExtractor,
    UploadedDocument,
    merge_values,
    new_vendor_row,
    normalize_values,
    to_vendor_values,
)
from services.document_ai.models import MAX_TOTAL_BYTES

IUP_PAYLOAD = {
    "document_type": "IUP", "vendor": None,
    "nib_nomor": None, "golongan": "Batuan", "nib_tanggal": None, "nib_lokasi": None,
    "surat_dukungan_nomor": None, "surat_dukungan_tanggal": None, "surat_dukungan_lokasi_quarry": None,
    "iup_nomor": "570/16-IUP.OP/DPMPTSP/IV/2023", "iup_nama": "PT SUMBER GUNUNG MAJU",
    "iup_bentuk_usaha": "PT", "iup_tanggal_terbit": "18/04/2023", "iup_periode": 5,
    "iup_tanggal_berakhir": "2028-04-16", "catatan": None,
}


class FakeModels:
    def __init__(self, response=None, error=None):
        self.response, self.error, self.calls = response, error, []

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.response


def extractor_with(response=None, error=None):
    models = FakeModels(response, error)
    return GeminiExtractor("key", "test-model", client=SimpleNamespace(models=models)), models


PDF = UploadedDocument("iup.pdf", b"%PDF-1.4 data", "application/pdf")


class MapperTest(unittest.TestCase):
    def test_fillable_columns_exist_in_database_schema(self):
        self.assertTrue(set(FILLABLE_COLUMNS) <= set(DB_COLS))

    def test_to_vendor_values_normalizes(self):
        doc = ExtractedDocument.model_validate_json(json.dumps(IUP_PAYLOAD))
        values = to_vendor_values(doc)
        self.assertEqual(values["iup_tanggal_terbit"], "2023-04-18")
        self.assertEqual(values["iup_periode"], "5")
        self.assertNotIn("vendor", values)  # null tidak ikut
        self.assertEqual(values["golongan"], "Batuan")

    def test_normalize_values_ignores_unknown_and_blank(self):
        self.assertEqual(normalize_values({"iup_nama": " PT A ", "foo": "x", "nib_lokasi": "-"}),
                         {"iup_nama": "PT A"})

    def test_merge_values_respects_overwrite_flag(self):
        existing = {"vendor": "ABADI", "iup_nama": "PT LAMA", "iup_nomor": ""}
        values = {"iup_nama": "PT BARU", "iup_nomor": "123"}
        keep = merge_values(existing, values, overwrite=False)
        self.assertEqual((keep["iup_nama"], keep["iup_nomor"]), ("PT LAMA", "123"))
        over = merge_values(existing, values, overwrite=True)
        self.assertEqual(over["iup_nama"], "PT BARU")
        self.assertEqual(over["vendor"], "ABADI")

    def test_new_vendor_row_has_all_columns(self):
        row = new_vendor_row({"iup_nama": "PT A"})
        self.assertEqual(set(row), set(DB_COLS))
        self.assertEqual(row["iup_nama"], "PT A")


class ExtractorTest(unittest.TestCase):
    def test_uses_parsed_response_and_sends_documents(self):
        parsed = ExtractedDocument.model_validate_json(json.dumps(IUP_PAYLOAD))
        extractor, models = extractor_with(SimpleNamespace(parsed=parsed, text=None))
        result = extractor.extract([PDF])
        self.assertEqual(result.iup_nama, "PT SUMBER GUNUNG MAJU")
        self.assertEqual(models.calls[0]["model"], "test-model")
        self.assertEqual(len(models.calls[0]["contents"]), 2)  # 1 berkas + teks perintah

    def test_falls_back_to_json_text(self):
        extractor, _ = extractor_with(SimpleNamespace(parsed=None, text=json.dumps(IUP_PAYLOAD)))
        self.assertEqual(extractor.extract([PDF]).iup_nomor, IUP_PAYLOAD["iup_nomor"])

    def test_empty_response_raises(self):
        extractor, _ = extractor_with(SimpleNamespace(parsed=None, text=""))
        with self.assertRaises(ExtractionError):
            extractor.extract([PDF])

    def test_api_error_is_wrapped(self):
        extractor, _ = extractor_with(error=RuntimeError("quota"))
        with self.assertRaisesRegex(ExtractionError, "quota"):
            extractor.extract([PDF])

    def test_rejects_bad_input(self):
        extractor, models = extractor_with(SimpleNamespace(parsed=None, text="{}"))
        with self.assertRaises(ExtractionError):
            extractor.extract([])
        with self.assertRaises(ExtractionError):
            extractor.extract([UploadedDocument("a.txt", b"x", "text/plain")])
        with self.assertRaises(ExtractionError):
            extractor.extract([UploadedDocument("big.pdf", b"0" * (MAX_TOTAL_BYTES + 1), "application/pdf")])
        self.assertEqual(models.calls, [])  # tidak ada panggilan API untuk input tidak valid


if __name__ == "__main__":
    unittest.main()
