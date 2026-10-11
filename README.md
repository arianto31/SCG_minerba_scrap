# Procurement Vendor Checker

Aplikasi Streamlit untuk mengelola data vendor, mengecek IUP-nya ke data Minerba (ESDM), dan mengisi data
otomatis dari Excel atau dari foto/PDF dokumen (dibaca Gemini).

## Menjalankan

1. Salin seluruh isi folder ini ke proyek Anda, **satu folder dengan `minerba_scraper.py`** (file scraper lama, tidak diubah).
2. `pip install -r requirements.txt`
3. Salin `.env.example` menjadi `.env`, isi `SUPABASE_URL`, `SUPABASE_KEY`, dan (opsional) `GEMINI_API_KEY`.
4. Jalankan isi `sql/schema.sql` sekali di Supabase (SQL Editor). Jika belum, aplikasi menampilkannya sendiri.
5. `streamlit run app.py`

Tes: `python -m unittest discover -s tests -t .`

## Struktur dan aturan dependensi

Dependensi hanya mengarah ke bawah: `ui` -> `services`/`repositories` -> `core`.
Lapisan `core`, `services`, dan `repositories` tidak mengimpor Streamlit, sehingga bisa diuji tanpa UI.

| Folder | Tanggung jawab | Cari di sini jika... |
|---|---|---|
| `app.py` | Titik masuk, menyusun tab | tab/halaman salah |
| `config.py` | Semua variabel `.env` | API key / nama model |
| `core/schema.py` | Daftar kolom, label, konstanta | menambah/mengubah kolom vendor |
| `core/validation.py` | Cocokkan ke Minerba, isi otomatis, countdown, remark | hasil Valid/"-" atau peringatan salah |
| `core/text_utils.py` | Normalisasi nama, tanggal, angka | format tanggal/angka bermasalah |
| `repositories/` | Semua akses Supabase | error database, query |
| `services/excel_export.py` / `excel_import.py` | Baca/tulis Excel | Excel tidak terbaca / tata letak salah |
| `services/document_ai/` | Ekstraksi dokumen dengan Gemini | hasil AI salah / ganti model |
| `ui/vendor_tab.py`, `ui/minerba_tab.py` | Merangkai tab | urutan tampilan |
| `ui/sections/` | Satu file = satu bagian layar | tombol/formulir tertentu |
| `ui/styles.py` | Warna baris, konfigurasi kolom | tampilan tabel |
| `ui/state.py` | Kunci `session_state` & konteks bersama | state saling menimpa |
| `tests/` | Unit test | setelah mengubah logika |

### Alur fitur upload dokumen AI

`ui/sections/document_upload.py` -> `services/document_ai/gemini_extractor.py` (kirim berkas + skema ke Gemini)
-> `mapper.py` (rapikan tanggal/angka) -> pratinjau & koreksi oleh user -> `core/validation.py` (cek ke Minerba)
-> `repositories/vendor_repository.py` (simpan).

- Ubah instruksi ke AI: `services/document_ai/prompts.py`
- Tambah field yang diekstrak: `models.py` (`ExtractedDocument` + `FILLABLE_COLUMNS`); nama field harus sama dengan nama kolom database
- Ganti model: `GEMINI_MODEL` di `.env`, atau ganti isi `create_extractor()` di `services/document_ai/__init__.py` untuk penyedia lain

### Menambah fitur baru

1. Logika murni -> `core/` atau `services/` (+ tes di `tests/`)
2. Akses data -> `repositories/`
3. Tampilan -> file baru di `ui/sections/` lalu panggil dari `ui/vendor_tab.py`
