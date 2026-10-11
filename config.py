"""Konfigurasi aplikasi: seluruh variabel lingkungan dibaca di sini (satu-satunya tempat)."""
import os

from dotenv import load_dotenv

load_dotenv(override=True)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Fitur ekstraksi dokumen (opsional). Tanpa API key, fitur upload dokumen otomatis dinonaktifkan.
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
# Model Gemini 2.5 dijadwalkan dimatikan 16 Oktober 2026 -> default memakai seri 3.x.
# Cek daftar model terbaru di https://ai.google.dev/gemini-api/docs/models
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite").strip()
