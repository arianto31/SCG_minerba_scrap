"""Table display: column configuration, row colors, and English labels for the ESDM columns."""
import pandas as pd
import streamlit as st

from core.schema import AUTO_COLS, DB_COLS, pretty_label
from core.vendor_status import STATUS_ATTENTION, STATUS_LABELS, STATUS_NOT_FOUND, row_status

ROW_RED = "background-color: rgba(248, 113, 113, 0.16)"
ROW_YELLOW = "background-color: rgba(251, 191, 36, 0.14)"
STATUS_COLUMN = "status"

_WA_DISPLAY_TEXT = r"https://wa\.me/(.*)"  # show only the number; the link still opens wa.me

_COLUMN_WIDTHS = {
    "vendor": "large", "nama_pic": "medium", "no_kontak": "medium", "golongan": "medium",
    "nib_lokasi": "large", "surat_dukungan_lokasi_quarry": "large",
    "iup_nama": "large", "remark": "large",
    "minerbaone": "small", "smart_comp": "small", "iup_countdown": "small", "iup_periode": "small",
}

_COLUMN_HELP = {
    "vendor": "Company that supplies the material.",
    "nama_pic": "Person in charge at the vendor.",
    "nib_nomor": "NIB = Nomor Induk Berusaha (business identification number), 13 digits.",
    "golongan": "Material group, e.g. Batuan, Pasir, Fly Ash.",
    "surat_dukungan_nomor": "Support letter (surat dukungan) from the quarry owner.",
    "iup_nama": "Company holding the IUP (mining business permit). Checked against MinerbaOne.",
    "iup_tanggal_berakhir": "Date the IUP stops being valid.",
    "smart_comp": "Smart Comp check result.",
    "remark": "Your notes. Expiry warnings are added automatically.",
}

# English labels for the scraped ESDM columns (the values stay as published by ESDM).
MINERBA_LABELS = {
    "nama_badan_usaha": "Company Name",
    "id_badan_usaha": "Company ID",
    "nomor_izin": "Permit Number",
    "jenis_izin": "Permit Type",
    "tahap_kegiatan": "Activity Stage",
    "golongan": "Material Group",
    "komoditas": "Commodity",
    "luas_ha": "Area (ha)",
    "tanggal_berlaku": "Valid From",
    "tanggal_berakhir": "Expiry Date",
    "status_cnc": "CnC Status",
    "lokasi": "Location",
    "kode_wiup": "WIUP Code",
    "jenis_badan_usaha": "Entity Type",
    "jenis_perizinan": "Permit Category",
    "alamat": "Address",
}

_MINERBA_WIDE = {"nama_badan_usaha", "lokasi", "alamat"}


def minerba_label(column: str) -> str:
    return MINERBA_LABELS.get(column, column.replace("_", " ").title())


def build_vendor_column_config(whatsapp_links: bool = False, status_column: bool = False) -> dict:
    """
    Readable labels, widths that fit the content, auto columns locked, IUP holder name pinned.
    whatsapp_links=True: the contact column becomes a WhatsApp link (display tables only; the data must
    already be converted with `core.phone.with_whatsapp_links`).
    status_column=True: also configure the display-only Status column.
    """
    config = {}
    if status_column:
        config[STATUS_COLUMN] = st.column_config.TextColumn(
            "Status", width=125, pinned=True,
            help="✅ found in MinerbaOne · ❌ IUP holder not found · ⚠️ IUP expiring or expired",
        )
    for column in DB_COLS:
        options = dict(label=pretty_label(column), width=_COLUMN_WIDTHS.get(column, "medium"))
        if column in _COLUMN_HELP:
            options["help"] = _COLUMN_HELP[column]
        if column == "no_kontak":
            if whatsapp_links:
                options["help"] = "Click to open a WhatsApp chat."
                config[column] = st.column_config.LinkColumn(display_text=_WA_DISPLAY_TEXT, **options)
            else:
                options["help"] = "Type the number (0812… or 62812…). It becomes a WhatsApp link in the vendor table."
                config[column] = st.column_config.TextColumn(**options)
            continue
        if column in AUTO_COLS:
            options["disabled"] = True
            options["help"] = "Filled automatically from MinerbaOne / the expiry date. Not editable."
        if column == "iup_nama":
            options["pinned"] = True
        config[column] = st.column_config.TextColumn(**options)
    return config


def with_status_column(df: pd.DataFrame) -> pd.DataFrame:
    """Display copy with a leading, human-readable Status column (so meaning never relies on color alone)."""
    out = df.copy()
    out.insert(0, STATUS_COLUMN, row_status(df).map(STATUS_LABELS))
    return out


def style_rows(df: pd.DataFrame):
    """Red: IUP holder filled in but not found in ESDM. Amber: IUP expiring soon or expired."""
    row_css = [
        ROW_RED if state == STATUS_NOT_FOUND else ROW_YELLOW if state == STATUS_ATTENTION else ""
        for state in row_status(df)
    ]
    css = pd.DataFrame([[c] * df.shape[1] for c in row_css], index=df.index, columns=df.columns)
    return df.style.apply(lambda _: css, axis=None)


def pretty_minerba_config(df: pd.DataFrame) -> dict:
    return {
        column: st.column_config.TextColumn(
            label=minerba_label(column), width="large" if column in _MINERBA_WIDE else "medium")
        for column in df.columns
    }


def table_height(rows: int, maximum: int = 440) -> int:
    """Fit short tables to their content instead of leaving empty space (row ~35px + header)."""
    return min(maximum, 38 + 35 * max(rows, 1) + 2)
