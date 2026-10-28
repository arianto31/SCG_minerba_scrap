"""App configuration: every environment variable is read here (and only here)."""
import os

from dotenv import load_dotenv

load_dotenv(override=True)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Login: 'username:hash;username2:hash2'. Generate with `python -m tools.hash_password`.
AUTH_USERS = os.getenv("AUTH_USERS", "").strip()

# Document extraction (optional). Without an API key, the AI document scan feature is disabled.
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
# Gemini 2.5 models are scheduled to shut down on 16 October 2026 -> the default uses the 3.x series.
# Latest models: https://ai.google.dev/gemini-api/docs/models
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash").strip()
