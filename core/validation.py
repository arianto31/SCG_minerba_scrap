"""Match vendors against the Minerba (ESDM) data, auto-fill IUP fields, count down to expiry, and add warnings."""
from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional

import pandas as pd
from rapidfuzz import fuzz, process

from core import renewal
from core.schema import ALL_AUTO_TAGS, AUTO_TAG, RENEWAL_COL, VALID, VALID_MANUAL
from core.text_utils import is_blank, normalize_name, parse_date

# Vendor columns filled from the ESDM table: (candidate column names, fallback keywords).
# The ESDM column names are Indonesian (source data), so the candidates/keywords stay Indonesian.
# Fallback keywords = list of alternatives; an alternative matches if all its words appear in the column name.
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
    """Matching and auto-fill settings."""
    threshold: int = 100                 # 100 = names must match exactly (after normalization)
    warn_days: int = 180                 # warn when the IUP expires within N days
    match_col: Optional[str] = None      # ESDM column compared with the vendor's IUP holder name
    field_map: Dict[str, Optional[str]] = field(default_factory=dict)  # vendor column -> ESDM column


# ---------------------------------------------------------------- ESDM column detection
def detect_column(columns, candidates, keywords) -> Optional[str]:
    """Guess the ESDM column matching a vendor column (exact names first, then keywords)."""
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
    """The ESDM column most likely to hold the IUP holder name."""
    found = detect_column(columns, ["nama_iup", "iup_nama", "nama_izin"], ["iup", "nama"])
    if found is None and "nama_badan_usaha" in columns:
        return "nama_badan_usaha"
    return found


def default_field_map(columns: List[str]) -> Dict[str, Optional[str]]:
    """Initial guess of vendor <-> ESDM column pairs."""
    return {
        target: detect_column(columns, candidates, keywords)
        for target, (candidates, keywords) in MINERBA_FIELDS.items()
    }


# ---------------------------------------------------------------- matching against ESDM
def _build_name_index(df_minerba: pd.DataFrame, match_col: str) -> Dict[str, list]:
    """Normalized name -> list of ESDM row labels."""
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
    """If one company holds several permits, use the one that expires last."""
    rows = df_minerba.loc[labels]
    if end_col and len(rows) > 1:
        end_dates = rows[end_col].map(parse_date)
        if end_dates.notna().any():
            rows = rows.loc[[end_dates.idxmax()]]
    return rows.iloc[0]


def _match_with_minerba(df: pd.DataFrame, df_minerba: pd.DataFrame, cfg: ValidationSettings) -> Dict[str, list]:
    """New values for the MINERBAONE column and the columns filled from ESDM."""
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
        out["minerbaone"][position] = VALID
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


def _plural_days(days: int) -> str:
    return f"{days} day" if days == 1 else f"{days} days"


def _expiry_warning(days: Optional[int], warn_days: int) -> Optional[str]:
    if days is None:
        return None
    if days < 0:
        return f"{AUTO_TAG} IUP expired {_plural_days(abs(days))} ago"
    if days <= warn_days:
        return f"{AUTO_TAG} IUP expires in {_plural_days(days)}"
    return None


def _manual_remark_parts(remark) -> List[str]:
    """Parts of the remark typed by hand (old automatic warnings, including legacy ones, are dropped)."""
    text = "" if pd.isna(remark) else str(remark)
    return [p for p in text.split(" | ") if p.strip() and not p.strip().startswith(ALL_AUTO_TAGS)]


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


# ---------------------------------------------------------------- IUP renewal tracker
def _apply_completed_renewals(df: pd.DataFrame) -> None:
    """
    A holder whose renewal tracker was completed and verified by a user:
    - keeps the new expiry date entered on verification while MinerbaOne still shows the old (earlier) one;
    - counts as verified ('Valid (manual)') even if MinerbaOne does not list the holder (yet).
    Applied to every row of that holder, so all vendors / PICs using it agree.
    """
    trackers = renewal.by_holder(df, RENEWAL_COL)
    if not trackers:
        return
    for label, name in df["iup_nama"].map(normalize_name).items():
        tracker = trackers.get(name)
        if tracker is None or not tracker.is_verified:
            continue
        if tracker.renewed_until and renewal.later_date(df.at[label, "iup_tanggal_berakhir"], tracker.renewed_until):
            df.at[label, "iup_tanggal_berakhir"] = tracker.renewed_until
            if tracker.new_iup_number:
                df.at[label, "iup_nomor"] = tracker.new_iup_number
        if df.at[label, "minerbaone"] != VALID:
            df.at[label, "minerbaone"] = VALID_MANUAL


# ---------------------------------------------------------------- main API
def validate_vendors(df_vendor: pd.DataFrame, df_minerba: pd.DataFrame, cfg: ValidationSettings) -> pd.DataFrame:
    """
    1. The vendor's IUP holder name is matched to the ESDM name column: match -> MINERBAONE 'Valid', else '-'.
    2. On a match, the vendor's IUP columns are filled from the ESDM data (cfg.field_map).
    3. IUP COUNTDOWN = days from today until the IUP expiry date.
    4. REMARK gets an automatic warning when the days left <= cfg.warn_days (or the IUP already expired).
    """
    df = df_vendor.copy()
    for column, values in _match_with_minerba(df, df_minerba, cfg).items():
        df[column] = pd.Series(values, index=df.index, dtype=object)
    _apply_completed_renewals(df)

    countdowns, remarks = _countdown_and_remarks(df, cfg.warn_days)
    df["iup_countdown"] = pd.Series(countdowns, index=df.index, dtype=object)
    df["remark"] = pd.Series(remarks, index=df.index, dtype=object)
    return df
