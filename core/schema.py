"""Skema data vendor: pemetaan kolom, label tampilan, dan konstanta domain."""
from typing import Dict, List, Tuple

# (grup, sub-kolom) pada header Excel bertingkat -> nama kolom database.
# Urutan dictionary = urutan kolom di tabel, Excel, dan seluruh aplikasi.
COLUMN_MAPPING: Dict[Tuple[str, str], str] = {
    ("VENDOR", ""): "vendor",
    ("NAMA PIC", ""): "nama_pic",
    ("NO KONTAK", ""): "no_kontak",
    ("NIB (NOMOR INDUK BERUSAHA)", "NOMOR"): "nib_nomor",
    ("NIB (NOMOR INDUK BERUSAHA)", "TANGGAL"): "nib_tanggal",
    ("NIB (NOMOR INDUK BERUSAHA)", "LOKASI"): "nib_lokasi",
    ("SURAT DUKUNGAN", "NOMOR"): "surat_dukungan_nomor",
    ("SURAT DUKUNGAN", "TANGGAL"): "surat_dukungan_tanggal",
    ("SURAT DUKUNGAN", "LOKASI QUARRY"): "surat_dukungan_lokasi_quarry",
    ("IUP (IZIN USAHA PERTAMBANGAN)", "NOMOR"): "iup_nomor",
    ("IUP (IZIN USAHA PERTAMBANGAN)", "NAMA"): "iup_nama",
    ("IUP (IZIN USAHA PERTAMBANGAN)", "BENTUK"): "iup_bentuk_usaha",
    ("IUP (IZIN USAHA PERTAMBANGAN)", "TANGGAL TERBIT"): "iup_tanggal_terbit",
    ("IUP (IZIN USAHA PERTAMBANGAN)", "PERIODE"): "iup_periode",
    ("IUP (IZIN USAHA PERTAMBANGAN)", "TANGGAL BERAKHIR"): "iup_tanggal_berakhir",
    ("IUP (IZIN USAHA PERTAMBANGAN)", "COUNTDOWN"): "iup_countdown",
    ("MINERBAONE", ""): "minerbaone",
    ("SMART COMP", ""): "smart_comp",
    ("Remark", ""): "remark",
}
DB_COLS: List[str] = list(COLUMN_MAPPING.values())
REVERSE_MAPPING: Dict[str, Tuple[str, str]] = {v: k for k, v in COLUMN_MAPPING.items()}

# Kolom bertipe tanggal (dinormalkan ke YYYY-MM-DD saat impor).
DATE_COLS = ["nib_tanggal", "surat_dukungan_tanggal", "iup_tanggal_terbit", "iup_tanggal_berakhir"]

# Kolom bertipe integer di database (desimal dibulatkan, mis. 5.116 -> 5).
INT_COLS = ["iup_periode", "iup_countdown"]

# Kolom yang diisi otomatis oleh sistem (tidak bisa diedit manual).
AUTO_COLS = ["minerbaone", "iup_countdown"]

# Penanda remark otomatis; remark yang diketik manual tidak ditimpa.
AUTO_TAG = "[PERINGATAN]"

# Nama tabel vendor bawaan (data lama sebelum ada fitur banyak tabel).
DEFAULT_TABLE = "Umum"

# Nama grup singkat untuk label di layar.
GROUP_SHORT = {
    "NIB (NOMOR INDUK BERUSAHA)": "NIB",
    "SURAT DUKUNGAN": "Surat Dukungan",
    "IUP (IZIN USAHA PERTAMBANGAN)": "IUP",
}


def pretty_label(db_col: str) -> str:
    """Label ringkas untuk kolom database, mis. 'iup_tanggal_terbit' -> 'IUP · Tanggal Terbit'."""
    group, sub = REVERSE_MAPPING[db_col]
    if sub:
        return f"{GROUP_SHORT.get(group, group)} · {sub.title()}"
    return group.title() if group.isupper() else group
