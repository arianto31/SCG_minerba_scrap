"""Vendor data schema: column mapping, display labels, and domain constants."""
from typing import Dict, List, Tuple

# (group, sub-column) in the two-level Excel header -> database column name.
# The Excel headers keep the company's standard (Indonesian) procurement format so existing files
# keep importing. Dictionary order = column order in the table, in Excel, and across the whole app.
COLUMN_MAPPING: Dict[Tuple[str, str], str] = {
    ("VENDOR", ""): "vendor",
    ("NAMA PIC", ""): "nama_pic",
    ("NO KONTAK", ""): "no_kontak",
    ("NIB (NOMOR INDUK BERUSAHA)", "NOMOR"): "nib_nomor",
    ("GOLONGAN", ""): "golongan",
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

# English labels shown on screen (NIB = business ID number, IUP = mining business permit).
DISPLAY_LABELS: Dict[str, str] = {
    "vendor": "Vendor",
    "nama_pic": "PIC Name",
    "no_kontak": "Contact No.",
    "nib_nomor": "NIB · Number",
    "golongan": "Material Group",
    "nib_tanggal": "NIB · Date",
    "nib_lokasi": "NIB · Location",
    "surat_dukungan_nomor": "Support Letter · Number",
    "surat_dukungan_tanggal": "Support Letter · Date",
    "surat_dukungan_lokasi_quarry": "Support Letter · Quarry Location",
    "iup_nomor": "IUP · Number",
    "iup_nama": "IUP · Holder Name",
    "iup_bentuk_usaha": "IUP · Entity Type",
    "iup_tanggal_terbit": "IUP · Issue Date",
    "iup_periode": "IUP · Term (years)",
    "iup_tanggal_berakhir": "IUP · Expiry Date",
    "iup_countdown": "IUP · Days Left",
    "minerbaone": "MinerbaOne",
    "smart_comp": "Smart Comp",
    "remark": "Remark",
}

# Date columns (normalized to YYYY-MM-DD on import).
DATE_COLS = ["nib_tanggal", "surat_dukungan_tanggal", "iup_tanggal_terbit", "iup_tanggal_berakhir"]

# Integer columns in the database (decimals are rounded, e.g. 5.116 -> 5).
INT_COLS = ["iup_periode", "iup_countdown"]

# Columns filled in by the system (not editable by hand).
AUTO_COLS = ["minerbaone", "iup_countdown"]

# Marker for automatic remarks; remarks typed by hand are never overwritten.
AUTO_TAG = "[WARNING]"
# Markers written by earlier versions of the app. Still recognised so old warnings get replaced.
LEGACY_AUTO_TAGS = ("[PERINGATAN]",)
ALL_AUTO_TAGS = (AUTO_TAG, *LEGACY_AUTO_TAGS)

# Value of the MINERBAONE column when the IUP holder was found in the ESDM data.
VALID = "Valid"

# Default vendor list name (stored data from before multiple lists existed; kept for compatibility).
DEFAULT_TABLE = "Umum"


def pretty_label(db_col: str) -> str:
    """Short English label for a database column, e.g. 'iup_tanggal_terbit' -> 'IUP · Issue Date'."""
    if db_col in DISPLAY_LABELS:
        return DISPLAY_LABELS[db_col]
    group, sub = REVERSE_MAPPING[db_col]
    return f"{group} · {sub.title()}" if sub else group.title()


def has_auto_tag(text) -> bool:
    """True if a remark contains an automatic warning (current or legacy marker)."""
    text = str(text or "")
    return any(tag in text for tag in ALL_AUTO_TAGS)
