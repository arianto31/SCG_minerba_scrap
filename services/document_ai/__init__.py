"""Fitur ekstraksi dokumen (foto/PDF) dengan AI. Titik masuk publik paket ini."""
import config

from .errors import ExtractionError, MissingApiKeyError
from .gemini_extractor import GeminiExtractor
from .mapper import merge_values, new_vendor_row, normalize_values, to_vendor_values
from .models import (
    ALLOWED_MIME_TYPES,
    DOCUMENT_TYPE_LABELS,
    FILLABLE_COLUMNS,
    DocumentType,
    ExtractedDocument,
    UploadedDocument,
)


def create_extractor() -> GeminiExtractor:
    """Buat extractor memakai konfigurasi .env. Ganti implementasi di sini untuk memakai model/penyedia lain."""
    return GeminiExtractor(api_key=config.GEMINI_API_KEY, model=config.GEMINI_MODEL)


__all__ = [
    "ALLOWED_MIME_TYPES", "DOCUMENT_TYPE_LABELS", "FILLABLE_COLUMNS", "DocumentType", "ExtractedDocument",
    "ExtractionError", "GeminiExtractor", "MissingApiKeyError", "UploadedDocument", "create_extractor",
    "merge_values", "new_vendor_row", "normalize_values", "to_vendor_values",
]
