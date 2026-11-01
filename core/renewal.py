"""IUP renewal tracker: step-by-step progress of an IUP extension, stored as JSON in the `iup_renewal` column.

The tracker belongs to an IUP holder, not to one row: when several rows (vendors / PICs) use the same holder,
they share one tracker. The most recently updated tracker among those rows wins.
"""
import json
import re
from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Dict, Iterable, List, Optional, Tuple

import pandas as pd

from core.text_utils import normalize_name, parse_date

# (step title, what "done" means). Typical path to an IUP extension in Indonesia.
RENEWAL_STEPS: Tuple[Tuple[str, str], ...] = (
    ("Prepare renewal documents",
     "Current IUP, company deeds, NIB, technical and environmental reports collected."),
    ("Submit the extension application",
     "Application submitted to the licensing authority (OSS / MinerbaOne)."),
    ("Document & technical review",
     "Authority checked the documents and evaluated the technical / environmental reports."),
    ("Fulfil requirements & pay fees",
     "Revision requests answered, guarantees placed and state fees (PNBP) paid."),
    ("Extension decree issued",
     "New IUP decree (SK) received with the new expiry date."),
)

TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M"
STALE_AFTER_DAYS = 14   # no progress for this long -> the tracker is flagged as stale


@dataclass(frozen=True)
class Step:
    done: bool = False
    updated: str = ""   # TIMESTAMP_FORMAT, when this step last changed
    note: str = ""


@dataclass(frozen=True)
class Renewal:
    steps: Tuple[Step, ...] = field(default_factory=lambda: tuple(Step() for _ in RENEWAL_STEPS))
    verified_on: str = ""      # TIMESTAMP_FORMAT, set when the user completed the renewal and verified the holder
    renewed_until: str = ""    # YYYY-MM-DD, new IUP expiry date entered on verification
    new_iup_number: str = ""

    # ---- progress
    @property
    def done_count(self) -> int:
        return sum(step.done for step in self.steps)

    @property
    def total(self) -> int:
        return len(self.steps)

    @property
    def all_done(self) -> bool:
        return self.done_count == self.total

    @property
    def is_verified(self) -> bool:
        return bool(self.verified_on)

    @property
    def is_empty(self) -> bool:
        return not self.is_verified and not any(s.done or s.note or s.updated for s in self.steps)

    @property
    def last_update(self) -> str:
        """Latest timestamp of any change (step or verification); '' when nothing happened yet."""
        stamps = [s.updated for s in self.steps if s.updated] + ([self.verified_on] if self.verified_on else [])
        return max(stamps) if stamps else ""

    @property
    def next_step(self) -> Optional[int]:
        """Index of the first open step (None when all are done)."""
        return next((i for i, step in enumerate(self.steps) if not step.done), None)


# ------------------------------------------------------------------ JSON <-> Renewal
def parse(text) -> Renewal:
    """JSON text from the database -> Renewal. Empty or broken text gives an empty tracker."""
    try:
        data = json.loads(text) if isinstance(text, str) and text.strip() else {}
    except (TypeError, ValueError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    raw_steps = data.get("steps") if isinstance(data.get("steps"), list) else []
    steps = []
    for i in range(len(RENEWAL_STEPS)):
        raw = raw_steps[i] if i < len(raw_steps) and isinstance(raw_steps[i], dict) else {}
        steps.append(Step(done=bool(raw.get("done")), updated=str(raw.get("updated") or ""),
                          note=str(raw.get("note") or "")))
    return Renewal(
        steps=tuple(steps),
        verified_on=str(data.get("verified_on") or ""),
        renewed_until=str(data.get("renewed_until") or ""),
        new_iup_number=str(data.get("new_iup_number") or ""),
    )


def dump(renewal: Renewal) -> str:
    """Renewal -> compact JSON text ('' for an empty tracker so the database column stays NULL)."""
    if renewal.is_empty:
        return ""
    return json.dumps({
        "steps": [{"done": s.done, "updated": s.updated, "note": s.note} for s in renewal.steps],
        "verified_on": renewal.verified_on,
        "renewed_until": renewal.renewed_until,
        "new_iup_number": renewal.new_iup_number,
    }, ensure_ascii=False, separators=(",", ":"))


# ------------------------------------------------------------------ changes
def now_stamp(now: Optional[datetime] = None) -> str:
    return (now or datetime.now()).strftime(TIMESTAMP_FORMAT)


def update_steps(renewal: Renewal, done: List[bool], notes: List[str], now: Optional[datetime] = None) -> Renewal:
    """Apply ticked boxes and notes. Only steps that actually changed get a new timestamp."""
    stamp = now_stamp(now)
    steps = []
    for step, is_done, note in zip(renewal.steps, done, notes):
        note = (note or "").strip()
        if step.done != bool(is_done) or step.note != note:
            steps.append(Step(done=bool(is_done), updated=stamp, note=note))
        else:
            steps.append(step)
    return replace(renewal, steps=tuple(steps))


def mark_verified(renewal: Renewal, renewed_until: str = "", new_iup_number: str = "",
                  now: Optional[datetime] = None) -> Renewal:
    return replace(renewal, verified_on=now_stamp(now), renewed_until=(renewed_until or "").strip(),
                   new_iup_number=(new_iup_number or "").strip())


def start_new_cycle(renewal: Renewal) -> Renewal:
    """Clear the steps for the next renewal, keeping the last verification (and its expiry date)."""
    return replace(renewal, steps=tuple(Step() for _ in RENEWAL_STEPS))


# ------------------------------------------------------------------ helpers
def days_since(stamp: str, now: Optional[datetime] = None) -> Optional[int]:
    try:
        then = datetime.strptime(stamp, TIMESTAMP_FORMAT)
    except (TypeError, ValueError):
        return None
    return ((now or datetime.now()).date() - then.date()).days


def is_stale(renewal: Renewal, now: Optional[datetime] = None) -> bool:
    """In progress, but nothing changed for STALE_AFTER_DAYS days."""
    if renewal.is_empty or renewal.all_done:
        return False
    days = days_since(renewal.last_update, now)
    return days is not None and days >= STALE_AFTER_DAYS


# "1. Document review; updated on 2026-02-01" (one entry per step; entries may be on separate lines or "|"-joined)
_REMARK_STEP = re.compile(
    r"(?<![\d.])(\d{1,2})\.\s*([^;|\n]*?)\s*;\s*updated(?:\s+on)?\s*:?\s*(\d{4}-\d{2}-\d{2})", re.IGNORECASE)


def from_remark(text) -> Renewal:
    """
    Steps written in a remark as "N. <step>; updated on YYYY-MM-DD" -> a tracker with those steps done.
    Unknown step numbers are ignored; the text after "N." is kept as the step note when it is not the
    standard step title. No matching entries -> empty tracker.
    """
    if not isinstance(text, str) or not text.strip():
        return Renewal()
    steps = list(Renewal().steps)
    for number, label, day in _REMARK_STEP.findall(text):
        index = int(number) - 1
        if not 0 <= index < len(steps) or pd.isna(parse_date(day)):
            continue
        label = label.strip()
        note = "" if label.lower() == RENEWAL_STEPS[index][0].lower() else label
        steps[index] = Step(done=True, updated=f"{day} 00:00", note=note)
    return Renewal(steps=tuple(steps))


def for_rows(renewal_texts: Iterable, remarks: Iterable) -> Tuple[Renewal, bool]:
    """
    Tracker of one holder: the saved JSON tracker when there is one, otherwise the steps written in its remarks.
    Returns (tracker, from_remark).
    """
    saved = latest(renewal_texts)
    if not saved.is_empty:
        return saved, False
    best = Renewal()
    for remark in remarks:
        candidate = from_remark(remark)
        if candidate.done_count > best.done_count or (
                candidate.done_count == best.done_count and candidate.last_update > best.last_update):
            best = candidate
    return best, not best.is_empty


def latest(texts: Iterable) -> Renewal:
    """The most recently updated tracker among several JSON texts (e.g. all rows of one holder)."""
    best = Renewal()
    for text in texts:
        candidate = parse(text)
        if candidate.last_update > best.last_update:
            best = candidate
    return best


def by_holder(df: pd.DataFrame, renewal_col: str = "iup_renewal") -> Dict[str, Renewal]:
    """Normalized IUP holder name -> its tracker (holders without a tracker are left out)."""
    if renewal_col not in df.columns or df.empty:
        return {}
    grouped: Dict[str, list] = {}
    for name, text in zip(df["iup_nama"].map(normalize_name), df[renewal_col]):
        if name and isinstance(text, str) and text.strip():
            grouped.setdefault(name, []).append(text)
    result = {}
    for name, texts in grouped.items():
        renewal = latest(texts)
        if not renewal.is_empty:
            result[name] = renewal
    return result


def later_date(current, candidate) -> bool:
    """True when `candidate` is a valid date later than `current` (or `current` is missing)."""
    new = parse_date(candidate)
    if pd.isna(new):
        return False
    old = parse_date(current)
    return pd.isna(old) or new > old
