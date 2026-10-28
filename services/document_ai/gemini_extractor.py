"""Permit document extraction with Gemini (`google-genai` SDK)."""
from typing import Optional, Sequence

from pydantic import ValidationError

from .errors import ExtractionError, MissingApiKeyError
from .models import ALLOWED_MIME_TYPES, MAX_TOTAL_BYTES, ExtractedDocument, UploadedDocument
from .prompts import SYSTEM_PROMPT, USER_PROMPT


class GeminiExtractor:
    """
    Reads document photos/PDFs and returns a structured `ExtractedDocument`.

    `client` can be injected (e.g. a fake for unit tests); otherwise it is created from `api_key`.
    """

    def __init__(self, api_key: str, model: str, client=None):
        if client is None:
            if not api_key:
                raise MissingApiKeyError("GEMINI_API_KEY is not set in the .env file")
            from google import genai  # imported lazily so other modules do not depend on the SDK
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
            # temperature deliberately not set: Google recommends the default for Gemini 3.x models
        )
        try:
            return self._client.models.generate_content(
                model=self._model,
                contents=[*parts, USER_PROMPT],  # text after media, as Google recommends
                config=config,
            )
        except Exception as exc:  # noqa: BLE001 - external service boundary; wrap anything
            raise ExtractionError(f"Could not reach Gemini (model {self._model}): {exc}") from exc


def _check_documents(documents: Sequence[UploadedDocument]) -> None:
    if not documents:
        raise ExtractionError("No file selected yet.")
    for doc in documents:
        if doc.mime_type not in ALLOWED_MIME_TYPES:
            raise ExtractionError(
                f"File '{doc.name}' ({doc.mime_type}) is not supported. "
                f"Use: {', '.join(ALLOWED_MIME_TYPES.values())}."
            )
    total = sum(len(doc.data) for doc in documents)
    if total > MAX_TOTAL_BYTES:
        raise ExtractionError(
            f"The files total {total / 1024 / 1024:.1f} MB, above the "
            f"{MAX_TOTAL_BYTES // 1024 // 1024} MB limit. Use smaller photos or fewer pages."
        )


def _parse_response(response) -> ExtractedDocument:
    parsed: Optional[object] = getattr(response, "parsed", None)
    if isinstance(parsed, ExtractedDocument):
        return parsed

    text = getattr(response, "text", None)
    if not text:
        raise ExtractionError("Gemini returned no result (it may have been blocked by a safety filter, or the document is empty).")
    try:
        return ExtractedDocument.model_validate_json(text)
    except ValidationError as exc:
        raise ExtractionError(f"Gemini's answer does not match the expected format: {exc}") from exc
