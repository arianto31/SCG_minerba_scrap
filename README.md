# QUICK Andesit — Procurement Vendor Checker

A Streamlit app to manage quarry vendor data, verify each vendor's IUP (mining business permit) against the
official MinerbaOne (ESDM) database, and fill in data automatically from Excel files or from photos/PDFs of
permit documents (read by Gemini).

## Running

1. `pip install -r requirements.txt` (Streamlit 1.50 or newer)
2. Copy `.env.example` to `.env` and fill in `SUPABASE_URL`, `SUPABASE_KEY`, `AUTH_USERS` (sign-in, required) and,
   optionally, `GEMINI_API_KEY`. Create a user with `python -m tools.hash_password` and paste the line into `.env`.
3. Run `sql/schema.sql` in Supabase (SQL Editor; safe to run again). If new columns are missing, the app shows the SQL itself.
4. `streamlit run app.py`

Tests: `python -m unittest discover -s tests -t .`

## Using the app

| Page | What you do there |
|---|---|
| **Vendors** | Pick or create a vendor list, see the summary cards (verified / not found / needs attention), search and filter the vendor table, download Excel, and add vendors in one of three tabs: **Type or edit**, **Import from Excel**, **Scan a document (AI)**. **Matching rules** sets the name similarity, the expiry warning window, and which MinerbaOne columns fill the IUP fields. |
| **MinerbaOne database** | Browse, search, and filter the scraped ESDM permits, download them, or **Refresh data** (re-scrapes MinerbaOne; takes a few minutes, existing data is kept if it fails). |

Row status: ✅ verified in MinerbaOne · ❌ IUP holder not found (red row) · ⚠️ IUP expiring or expired (amber row).

## Structure and dependency rule

Dependencies only point downwards: `ui` -> `services`/`repositories` -> `core`.
The `core`, `services` and `repositories` layers never import Streamlit, so they can be tested without a UI.

| Path | Responsibility | Look here when... |
|---|---|---|
| `app.py` | Entry point, sidebar, page navigation | a page/menu is wrong |
| `.streamlit/config.toml` | Theme (colors, font), upload limit | changing the look |
| `ui/theme.py` | Global CSS + HTML building blocks (header, KPI cards, steps, legend) | styling a component |
| `config.py` | Every `.env` variable | API keys / model name |
| `core/schema.py` | Columns, English display labels, constants | adding/changing a vendor column |
| `core/validation.py` | Match to Minerba, auto-fill, countdown, remark warnings | wrong Valid/"-" result or warnings |
| `core/vendor_status.py` | Row status used by cards, filters and colors | counts/colors look wrong |
| `core/text_utils.py` | Name, date and number normalization | date/number format problems |
| `core/auth.py` / `ui/login.py` / `tools/hash_password.py` | Password hashing, sign-in page, hash generator | cannot sign in / user setup |
| `core/phone.py` | Contact number -> WhatsApp link | wrong/empty WA link |
| `core/filtering.py` | Table search and per-column filters (case-insensitive) | filters find nothing |
| `repositories/` | All Supabase access | database errors, queries |
| `minerba_scraper.py` | Async ESDM scraper with adaptive concurrency | slow scraping / 429 errors / missing ESDM data |
| `services/excel_export.py` / `excel_import.py` | Excel read/write (company two-level header format) | Excel not read / wrong layout |
| `services/document_ai/` | Document extraction with Gemini | wrong AI results / switching model |
| `ui/vendor_tab.py`, `ui/minerba_tab.py` | Page layouts | order of sections |
| `ui/sections/` | One file = one part of the screen | a specific button/form |
| `ui/styles.py` | Row colors, column config (incl. WA links), ESDM column labels | table appearance |
| `ui/scrape_progress.py` | Scraping progress card (HTML/CSS) | progress display |
| `ui/state.py` | `session_state` keys & shared context | state overwriting itself |
| `tests/` | Unit tests | after changing logic |

### Compatibility notes

- Database column names, the default list name `Umum`, and the Excel template headers stay in the original
  (Indonesian) format so existing data and files keep working. The Excel importer also accepts English headers.
- Automatic remark warnings now start with `[WARNING]`; old `[PERINGATAN]` warnings are recognised and replaced.

### AI document upload flow

`ui/sections/document_upload.py` -> `services/document_ai/gemini_extractor.py` (sends files + schema to Gemini)
-> `mapper.py` (cleans dates/numbers) -> user review & corrections -> `core/validation.py` (MinerbaOne check)
-> `repositories/vendor_repository.py` (save).

- Change the AI instructions: `services/document_ai/prompts.py`
- Extract a new field: `models.py` (`ExtractedDocument` + `FILLABLE_COLUMNS`); field names must equal database column names
- Change the model: `GEMINI_MODEL` in `.env`, or replace `create_extractor()` in `services/document_ai/__init__.py` for another provider

### Adding a feature

1. Pure logic -> `core/` or `services/` (+ tests in `tests/`)
2. Data access -> `repositories/`
3. Screen -> a new file in `ui/sections/`, called from `ui/vendor_tab.py`
