"""Ekstraksi data dokumen perizinan dengan Gemini (SDK `google-genai`)."""
from typing import Optional, Sequence

from pydantic import ValidationError

from .errors import ExtractionError, MissingApiKeyError
from .models import ALLOWED_MIME_TYPES, MAX_TOTAL_BYTES, ExtractedDocument, UploadedDocument
from .prompts import SYSTEM_PROMPT, USER_PROMPT


class GeminiExtractor:
    """
    Membaca foto/PDF dokumen dan mengembalikan `ExtractedDocument` (terstruktur).

    `client` dapat diinjeksi (mis. objek palsu untuk unit test); jika kosong dibuat dari `api_key`.
    """

    def __init__(self, api_key: str, model: str, client=None):
        if client is None:
            if not api_key:
                raise MissingApiKeyError("GEMINI_API_KEY belum diatur di file .env")
            from google import genai  # diimpor saat dibutuhkan agar modul lain tidak bergantung pada SDK
            client = genai.Client(api_key=api_key)
        self._client = client
        self._model = model

    def extract(self, documents: Sequence[UploadedDocument]) -> ExtractedDocument:
        _check_documents(documents)
        return _parse_response(self._generate(documents))

    def _generate(self, documents: Sequence[UploadedDocument]):
        from google.genai import types

        parts = [types.Part.from_bytes(data=doc.data, mime_type=doc.mime_type) for doc in documents]
        config = types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            response_mime_type="application/json",
            response_schema=ExtractedDocument,
            # temperature sengaja tidak diatur: Google menyarankan nilai bawaan untuk model Gemini 3.x
        )
        try:
            return self._client.models.generate_content(
                model=self._model,
                contents=[*parts, USER_PROMPT],  # teks setelah media sesuai saran Google
                config=config,
            )
        except Exception as exc:  # noqa: BLE001 - batas dengan layanan eksternal; apa pun dibungkus
            raise ExtractionError(f"Gagal menghubungi Gemini (model {self._model}): {exc}") from exc


def _check_documents(documents: Sequence[UploadedDocument]) -> None:
    if not documents:
        raise ExtractionError("Belum ada berkas yang dipilih.")
    for doc in documents:
        if doc.mime_type not in ALLOWED_MIME_TYPES:
            raise ExtractionError(
                f"Format berkas '{doc.name}' ({doc.mime_type}) tidak didukung. "
                f"Gunakan: {', '.join(ALLOWED_MIME_TYPES.values())}."
            )
    total = sum(len(doc.data) for doc in documents)
    if total > MAX_TOTAL_BYTES:
        raise ExtractionError(
            f"Total ukuran berkas {total / 1024 / 1024:.1f} MB melebihi batas "
            f"{MAX_TOTAL_BYTES // 1024 // 1024} MB. Kecilkan ukuran foto atau kurangi jumlah halaman."
        )


def _parse_response(response) -> ExtractedDocument:
    parsed: Optional[object] = getattr(response, "parsed", None)
    if isinstance(parsed, ExtractedDocument):
        return parsed

    text = getattr(response, "text", None)
    if not text:
        raise ExtractionError("Gemini tidak mengembalikan hasil (mungkin diblokir filter keamanan atau dokumen kosong).")
    try:
        return ExtractedDocument.model_validate_json(text)
    except ValidationError as exc:
        raise ExtractionError(f"Format hasil dari Gemini tidak sesuai skema: {exc}") from exc
