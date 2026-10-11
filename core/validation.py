"""Pencocokan vendor ke data Minerba (ESDM), pengisian otomatis, countdown, dan peringatan IUP."""
from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional

import pandas as pd
from rapidfuzz import fuzz, process

from core.schema import AUTO_TAG
from core.text_utils import is_blank, normalize_name, parse_date

# Kolom vendor yang diisi dari tabel ESDM: (nama kolom kandidat, kata kunci cadangan).
# Kata kunci cadangan = daftar alternatif; satu alternatif lolos jika semua katanya ada di nama kolom.
MINERBA_FIELDS = {
    "iup_nomor": (["nomor_sk", "no_sk", "nomor_iup", "no_iup", "nomor"], [["nomor"]]),
    "iup_bentuk_usaha": (["bentuk_usaha", "bentuk_badan_usaha", "jenis_badan_usaha"], [["bentuk"]]),
    "iup_tanggal_terbit": (
        ["tanggal_terbit", "tgl_terbit", "tanggal_berlaku_awal", "tgl_berlaku_awal", "tanggal_awal",
         "tanggal_mulai", "tanggal_sk", "tgl_sk", "tanggal_izin", "tgl_izin", "tanggal_penerbitan",
         "tgl_penerbitan", "tanggal_mulai_berlaku", "tanggal_berlaku", "tgl_berlaku"],
        [["awal"], ["terbit"], ["mulai"]],
    ),
    "iup_periode": (["periode", "jangka_waktu"], [["periode"]]),
    "iup_tanggal_berakhir": (
        ["tanggal_berakhir", "tgl_berakhir", "tanggal_berlaku_akhir", "tgl_berlaku_akhir", "tanggal_akhir"],
        [["akhir"], ["berakhir"], ["kadaluarsa"]],
    ),
}


@dataclass(frozen=True)
class ValidationSettings:
    """Pengaturan pencocokan & pengisian otomatis."""
    threshold: int = 100                 # 100 = nama harus sama persis (setelah dinormalkan)
    warn_days: int = 180                 # beri peringatan jika IUP berakhir dalam N hari
    match_col: Optional[str] = None      # kolom ESDM yang dicocokkan dengan IUP NAMA vendor
    field_map: Dict[str, Optional[str]] = field(default_factory=dict)  # kolom vendor -> kolom ESDM


# ---------------------------------------------------------------- deteksi kolom ESDM
def detect_column(columns, candidates, keywords) -> Optional[str]:
    """Tebak kolom ESDM yang sepadan dengan kolom vendor (nama persis dulu, lalu kata kunci)."""
    def simplify(text):
        return "".join(ch for ch in str(text).lower() if ch.isalnum())

    lookup = {simplify(c): c for c in columns}
    for candidate in candidates:
        if simplify(candidate) in lookup:
            return lookup[simplify(candidate)]

    keyword_sets = keywords if keywords and isinstance(keywords[0], list) else [keywords]
    for words in keyword_sets:
        for column in columns:
            if all(word in str(column).lower() for word in words):
                return column
    return None


def default_match_column(columns: List[str]) -> Optional[str]:
    """Kolom ESDM yang paling mungkin berisi nama IUP."""
    found = detect_column(columns, ["nama_iup", "iup_nama", "nama_izin"], ["iup", "nama"])
    if found is None and "nama_badan_usaha" in columns:
        return "nama_badan_usaha"
    return found


def default_field_map(columns: List[str]) -> Dict[str, Optional[str]]:
    """Tebakan awal pasangan kolom vendor <-> ESDM."""
    return {
        target: detect_column(columns, candidates, keywords)
        for target, (candidates, keywords) in MINERBA_FIELDS.items()
    }


# ---------------------------------------------------------------- pencocokan ke ESDM
def _build_name_index(df_minerba: pd.DataFrame, match_col: str) -> Dict[str, list]:
    """Nama ternormalisasi -> daftar label baris ESDM."""
    index: Dict[str, list] = {}
    for label, name in df_minerba[match_col].map(normalize_name).items():
        if name:
            index.setdefault(name, []).append(label)
    return index


def _find_key(name: str, index: Dict[str, list], threshold: int) -> Optional[str]:
    if not name:
        return None
    if name in index:
        return name
    if threshold < 100 and index:
        best = process.extractOne(name, list(index), scorer=fuzz.ratio)
        if best and best[1] >= threshold:
            return best[0]
    return None


def _pick_best_row(df_minerba: pd.DataFrame, labels: list, end_col: Optional[str]) -> pd.Series:
    """Jika satu badan usaha punya beberapa izin, pakai yang paling akhir berakhirnya."""
    rows = df_minerba.loc[labels]
    if end_col and len(rows) > 1:
        end_dates = rows[end_col].map(parse_date)
        if end_dates.notna().any():
            rows = rows.loc[[end_dates.idxmax()]]
    return rows.iloc[0]


def _match_with_minerba(df: pd.DataFrame, df_minerba: pd.DataFrame, cfg: ValidationSettings) -> Dict[str, list]:
    """Hasilkan nilai baru untuk kolom MINERBAONE dan kolom yang diisi dari ESDM."""
    active = {target: source for target, source in cfg.field_map.items() if source}
    out = {col: df[col].tolist() for col in ["minerbaone", *active]}
    out["minerbaone"] = ["-"] * len(df)

    if df_minerba.empty or not cfg.match_col or cfg.match_col not in df_minerba.columns:
        return out

    index = _build_name_index(df_minerba, cfg.match_col)
    end_col = active.get("iup_tanggal_berakhir")

    for position, name in enumerate(df["iup_nama"].tolist()):
        key = _find_key(normalize_name(name), index, cfg.threshold)
        if key is None:
            continue
        out["minerbaone"][position] = "Valid"
        row = _pick_best_row(df_minerba, index[key], end_col)
        for target, source in active.items():
            value = str(row.get(source, "")).strip()
            if not is_blank(value):
                out[target][position] = value
    return out


# ---------------------------------------------------------------- countdown & remark
def _days_until(end_date, today: pd.Timestamp) -> Optional[int]:
    parsed = parse_date(end_date)
    if pd.isna(parsed):
        return None
    return (parsed.normalize() - today).days


def _expiry_warning(days: Optional[int], warn_days: int) -> Optional[str]:
    if days is None:
        return None
    if days < 0:
        return f"{AUTO_TAG} IUP sudah berakhir {abs(days)} hari yang lalu"
    if days <= warn_days:
        return f"{AUTO_TAG} IUP akan berakhir {days} hari lagi"
    return None


def _manual_remark_parts(remark) -> List[str]:
    """Bagian remark yang diketik manual (peringatan otomatis lama dibuang)."""
    text = "" if pd.isna(remark) else str(remark)
    return [p for p in text.split(" | ") if p.strip() and not p.startswith(AUTO_TAG)]


def _countdown_and_remarks(df: pd.DataFrame, warn_days: int):
    today = pd.Timestamp(date.today())
    countdowns, remarks = [], []
    for end_date, remark in zip(df["iup_tanggal_berakhir"], df["remark"]):
        days = _days_until(end_date, today)
        warning = _expiry_warning(days, warn_days)
        parts = ([warning] if warning else []) + _manual_remark_parts(remark)
        countdowns.append("" if days is None else str(days))
        remarks.append(" | ".join(parts))
    return countdowns, remarks


# ---------------------------------------------------------------- API utama
def validate_vendors(df_vendor: pd.DataFrame, df_minerba: pd.DataFrame, cfg: ValidationSettings) -> pd.DataFrame:
    """
    1. IUP NAMA vendor dicocokkan ke kolom nama ESDM: cocok -> MINERBAONE 'Valid', tidak -> '-'.
    2. Jika cocok, kolom IUP vendor diisi dari data ESDM (cfg.field_map).
    3. IUP COUNTDOWN = sisa hari dari hari ini sampai IUP TANGGAL BERAKHIR.
    4. REMARK diberi peringatan otomatis jika sisa hari <= cfg.warn_days (atau sudah lewat).
    """
    df = df_vendor.copy()
    for column, values in _match_with_minerba(df, df_minerba, cfg).items():
        df[column] = pd.Series(values, index=df.index, dtype=object)

    countdowns, remarks = _countdown_and_remarks(df, cfg.warn_days)
    df["iup_countdown"] = pd.Series(countdowns, index=df.index, dtype=object)
    df["remark"] = pd.Series(remarks, index=df.index, dtype=object)
    return df
