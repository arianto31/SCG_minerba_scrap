"""Find saved records related to a vendor / IUP holder name, so users can spot duplicates before saving."""
from typing import List, Tuple

import pandas as pd
from rapidfuzz import fuzz

from core.text_utils import normalize_name

MATCH_COLUMN = "match"     # added to the result: why the row was listed
_SIMILAR_SCORE = 88        # fuzzy score (0-100) treated as "similar name"
_MIN_CONTAIN_LEN = 4       # shorter names are not checked with "contains" (too many hits)


def name_score(first, second) -> int:
    """0-100. 100 = same name after normalization (PT/CV, punctuation and case ignored)."""
    a, b = normalize_name(first), normalize_name(second)
    if not a or not b:
        return 0
    if a == b:
        return 100
    if min(len(a), len(b)) >= _MIN_CONTAIN_LEN and (a in b or b in a):
        return 95
    return int(fuzz.ratio(a, b))


def _reason(label: str, score: int) -> str:
    return f"Same {label}" if score == 100 else f"Similar {label}"


def find_related(df: pd.DataFrame, vendor: str = "", holder: str = "", limit: int = 15) -> pd.DataFrame:
    """
    Rows of `df` whose vendor or IUP holder looks like the given names.
    Sorted by best match first; a `match` column explains why each row is listed.
    """
    if df.empty or not (normalize_name(vendor) or normalize_name(holder)):
        return df.iloc[0:0].assign(**{MATCH_COLUMN: []})

    hits: List[Tuple[int, object, str]] = []
    for label, row in df.iterrows():
        reasons, best = [], 0
        for name, column, what in ((holder, "iup_nama", "IUP holder"), (vendor, "vendor", "vendor")):
            score = name_score(name, row.get(column, ""))
            if score >= _SIMILAR_SCORE:
                reasons.append(_reason(what, score))
                best = max(best, score + (1 if column == "iup_nama" else 0))  # holder matches first
        if reasons:
            hits.append((best, label, " · ".join(reasons)))

    hits.sort(key=lambda hit: -hit[0])
    hits = hits[:limit]
    out = df.loc[[label for _, label, _ in hits]].copy()
    out[MATCH_COLUMN] = [reason for _, _, reason in hits]
    return out


def row_keys(df: pd.DataFrame) -> List[Tuple[str, str]]:
    """(vendor, holder) normalized, one per row."""
    return [(normalize_name(v), normalize_name(h)) for v, h in zip(df["vendor"], df["iup_nama"])]


def new_rows(edited: pd.DataFrame, saved: pd.DataFrame) -> pd.DataFrame:
    """Rows of `edited` whose vendor + holder pair does not exist in `saved` (added or renamed rows)."""
    existing = set(row_keys(saved))
    keep = [key not in existing and any(key) for key in row_keys(edited)]
    return edited[keep]


def related_to_new_rows(edited: pd.DataFrame, saved: pd.DataFrame, limit: int = 15) -> pd.DataFrame:
    """Saved rows related to any row that is new in `edited` (used before saving the editor table)."""
    parts = []
    for _, row in new_rows(edited, saved).iterrows():
        found = find_related(saved, row.get("vendor", ""), row.get("iup_nama", ""), limit)
        if not found.empty:
            parts.append(found.assign(**{MATCH_COLUMN: found[MATCH_COLUMN] + f" as new row '{_short(row)}'"}))
    if not parts:
        return saved.iloc[0:0].assign(**{MATCH_COLUMN: []})
    combined = pd.concat(parts)
    return combined[~combined.index.duplicated()].head(limit)


def _short(row) -> str:
    return str(row.get("iup_nama") or row.get("vendor") or "").strip()[:40]
