"""Document extraction exceptions (so the UI can show friendly messages)."""


class ExtractionError(Exception):
    """Extraction failed (invalid file, AI service error, or unreadable result)."""


class MissingApiKeyError(ExtractionError):
    """The Gemini API key is not set."""
