"""Impor data vendor dari Excel. Mendukung header 1 baris maupun header 2 tingkat (sel digabung)."""
import io
from dataclasses import dataclass
from datetime import date, datetime
from typing import Dict, List, Optional, Tuple

import pandas as pd

from core.schema import DATE_COLS, DB_COLS, INT_COLS
from core.text_utils import clean_key, is_blank, to_int_str, to_iso_date

# Kunci = teks header yang sudah dibersihkan (huruf kecil, tanpa spasi/tanda baca/isi kurung).
HEADER_ALIASES = {
    "vendor": "vendor", "namavendor": "vendor",
    "namapic": "nama_pic", "pic": "nama_pic",
    "nokontak": "no_kontak", "kontak": "no_kontak", "nohp": "no_kontak", "nomorkontak": "no_kontak",
    "nibnomor": "nib_nomor", "nib": "nib_nomor",
    "golongan": "golongan", "golonganusaha": "golongan", "jenisgolongan": "golongan",
    "nibtanggal": "nib_tanggal",
    "niblokasi": "nib_lokasi", "lokasi": "nib_lokasi",
    "suratdukungannomor": "surat_dukungan_nomor",
    "suratdukungantanggal": "surat_dukungan_tanggal",
    "suratdukunganlokasiquarry": "surat_dukungan_lokasi_quarry",
    "suratdukunganlokasi": "surat_dukungan_lokasi_quarry",
    "lokasiquarry": "surat_dukungan_lokasi_quarry",
    "iupnomor": "iup_nomor",
    "iupnama": "iup_nama",
    "iupbentuk": "iup_bentuk_usaha", "iupbentukusaha": "iup_bentuk_usaha",
    "iuptanggal": "iup_tanggal_terbit", "iuptanggalterbit": "iup_tanggal_terbit",
    "iupperiode": "iup_periode", "periode": "iup_periode",
    "iuptanggalberakhir": "iup_tanggal_berakhir", "tanggalberakhir": "iup_tanggal_berakhir",
    "iupcountdown": "iup_countdown", "countdown": "iup_countdown",
    "minerbaone": "minerbaone",
    "smartcomp": "smart_comp",
    "remark": "remark", "keterangan": "remark", "catatan": "remark",
}

# Label sub-header yang menandakan baris kedua pada header 2 tingkat.
SUB_LABELS = {"nomor", "tanggal", "lokasi", "lokasiquarry", "nama", "bentuk", "periode",
              "tanggalterbit", "tanggalberakhir", "countdown"}

_MAX_HEADER_SEARCH_ROWS = 30


@dataclass
class ImportResult:
    data: pd.DataFrame                 # kolom = DB_COLS, indeks = NO
    mapped: List[Tuple[str, str]]      # (label di Excel, kolom database)
    unmapped: List[str]                # label kolom yang tidak dikenali


def parse_vendor_excel(data: bytes) -> ImportResult:
    """Baca file Excel vendor. Melempar ValueError jika kolom VENDOR tidak ditemukan."""
    raw = pd.read_excel(io.BytesIO(data), header=None, dtype=object)
    if raw.empty:
        raise ValueError("File Excel kosong.")

    header_row = _find_header_row(raw)
    sub_row = _find_sub_header(raw, header_row)
    column_map, mapped, unmapped = _map_columns(raw.iloc[header_row].tolist(), sub_row)

    first_data_row = header_row + (2 if sub_row is not None else 1)
    df = _build_dataframe(raw.iloc[first_data_row:], column_map)
    return ImportResult(data=df, mapped=mapped, unmapped=unmapped)


# ------------------------------------------------------------------ header
def _find_header_row(raw: pd.DataFrame) -> int:
    for i in range(min(len(raw), _MAX_HEADER_SEARCH_ROWS)):
        if any(clean_key(v) == "vendor" for v in raw.iloc[i].tolist() if pd.notna(v)):
            return i
    raise ValueError("Kolom 'VENDOR' tidak ditemukan pada 30 baris pertama. Pastikan header sesuai template.")


def _find_sub_header(raw: pd.DataFrame, header_row: int) -> Optional[list]:
    """Baris sub-header (mis. NOMOR/TANGGAL) jika header 2 tingkat; None jika header 1 baris."""
    if header_row + 1 >= len(raw):
        return None
    next_row = raw.iloc[header_row + 1].tolist()
    labels = [clean_key(v) for v in next_row if pd.notna(v)]
    return next_row if sum(label in SUB_LABELS for label in labels) >= 2 else None


def _header_to_db(key: str) -> Optional[str]:
    if key in HEADER_ALIASES:
        return HEADER_ALIASES[key]
    if "countdown" in key:
        return "iup_countdown"
    if ("minerba" in key or "smartcomp" in key) and "tanggal" in key:
        return "iup_tanggal_berakhir"
    return None


def _map_columns(group_row: list, sub_row: Optional[list]):
    """Petakan setiap kolom Excel ke kolom database. Mengembalikan (index->kolom db, terpetakan, tak dikenal)."""
    column_map: Dict[int, str] = {}
    mapped: List[Tuple[str, str]] = []
    unmapped: List[str] = []
    last_group = ""

    for j, group_cell in enumerate(group_row):
        group = "" if pd.isna(group_cell) else str(group_cell).strip()
        sub = ""
        if sub_row is not None and not pd.isna(sub_row[j]):
            sub = str(sub_row[j]).strip()
        if group:
            last_group = group
        effective_group = group if (group or not sub) else last_group  # sel grup digabung -> ambil dari kiri

        label = f"{effective_group} {sub}".strip()
        if not label:
            continue
        db_col = _header_to_db(clean_key(effective_group) + clean_key(sub))
        if db_col and db_col not in column_map.values():
            column_map[j] = db_col
            mapped.append((label, db_col))
        elif clean_key(label) != "no":
            unmapped.append(label)
    return column_map, mapped, unmapped


# ------------------------------------------------------------------ data
def _normalize_cell(db_col: str, value) -> str:
    if is_blank(value):
        return ""
    if isinstance(value, (datetime, date)):
        text = value.strftime("%Y-%m-%d")
    elif isinstance(value, float) and value.is_integer():
        text = str(int(value))
    else:
        text = str(value).strip()

    if db_col in DATE_COLS:
        return to_iso_date(text)
    if db_col in INT_COLS:
        return to_int_str(text)
    return text


def _build_dataframe(body: pd.DataFrame, column_map: Dict[int, str]) -> pd.DataFrame:
    rows = []
    for _, source in body.iterrows():
        record = {col: "" for col in DB_COLS}
        for j, db_col in column_map.items():
            record[db_col] = _normalize_cell(db_col, source.iloc[j])
        record["minerbaone"] = ""      # dihitung ulang oleh sistem
        record["iup_countdown"] = ""   # dihitung ulang oleh sistem
        if record["vendor"] or record["iup_nama"]:
            rows.append(record)

    df = pd.DataFrame(rows, columns=DB_COLS)
    df.index = df.index + 1
    df.index.name = "NO"
    return df
