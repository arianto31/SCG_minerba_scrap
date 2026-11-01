"""Vendor row status (verified / not found / needs attention), shared by the summary cards, filters and colors."""
from dataclasses import dataclass

import pandas as pd

from core.schema import VALID, VALID_MANUAL, has_auto_tag

STATUS_VERIFIED = "verified"        # IUP holder found in MinerbaOne (or verified by hand), no warning
STATUS_NOT_FOUND = "not_found"      # IUP holder filled in but not found in MinerbaOne
STATUS_ATTENTION = "attention"      # IUP expiring soon or already expired
STATUS_INCOMPLETE = "incomplete"    # no IUP holder name yet

STATUS_LABELS = {
    STATUS_VERIFIED: "✅ Verified",
    STATUS_NOT_FOUND: "❌ Not found",
    STATUS_ATTENTION: "⚠️ Expiring",
    STATUS_INCOMPLETE: "○ No IUP name",
}


def _has_iup_name(df: pd.DataFrame) -> pd.Series:
    return df["iup_nama"].astype(str).str.strip() != ""


def is_valid(df: pd.DataFrame) -> pd.Series:
    return df["minerbaone"].isin([VALID, VALID_MANUAL])


def is_not_found(df: pd.DataFrame) -> pd.Series:
    return _has_iup_name(df) & ~is_valid(df)


def needs_attention(df: pd.DataFrame) -> pd.Series:
    return df["remark"].map(has_auto_tag).astype(bool)


def row_status(df: pd.DataFrame) -> pd.Series:
    """One status per row. 'Not found' wins over 'expiring' (same priority as the row colors)."""
    status = pd.Series(STATUS_INCOMPLETE, index=df.index, dtype=object)
    status[is_valid(df)] = STATUS_VERIFIED
    status[needs_attention(df)] = STATUS_ATTENTION
    status[is_not_found(df)] = STATUS_NOT_FOUND
    return status


@dataclass(frozen=True)
class StatusSummary:
    total: int          # rows with an IUP holder name
    verified: int
    not_found: int
    attention: int


def summarize(df: pd.DataFrame) -> StatusSummary:
    if df.empty:
        return StatusSummary(0, 0, 0, 0)
    return StatusSummary(
        total=int(_has_iup_name(df).sum()),
        verified=int(is_valid(df).sum()),
        not_found=int(is_not_found(df).sum()),
        attention=int(needs_attention(df).sum()),
    )
