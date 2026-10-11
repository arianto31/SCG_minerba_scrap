"""Exception khusus fitur ekstraksi dokumen (agar UI bisa menampilkan pesan yang ramah)."""


class ExtractionError(Exception):
    """Ekstraksi gagal (berkas tidak valid, layanan AI error, atau hasil tidak terbaca)."""


class MissingApiKeyError(ExtractionError):
    """API key Gemini belum diatur."""
