"""Material group (golongan) options: a fixed base list plus any group already used in saved records.

A new group exists once a record that uses it is saved, so it then shows up in every dropdown.
Spelling is kept uniform: a typed value that matches an option (ignoring case and extra spaces) becomes
that option's spelling.
"""
from typing import Iterable, List

import pandas as pd

BASE_GROUPS = ("Batuan", "Pasir", "Fly Ash")


def clean(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return " ".join(str(value).split())


def _key(value) -> str:
    return clean(value).casefold()


def build_options(*sources: Iterable) -> List[str]:
    """Base groups first (in their order), then every other group found in `sources`, sorted. No duplicates."""
    options = {_key(g): g for g in BASE_GROUPS}
    others = {}
    for source in sources:
        for value in source:
            text = clean(value)
            if text and _key(text) not in options:
                others.setdefault(_key(text), text)
    return list(options.values()) + sorted(others.values(), key=str.casefold)


def canonical(value, options: Iterable[str]) -> str:
    """The option with the same name (case / spaces ignored), otherwise the cleaned value itself."""
    text = clean(value)
    if not text:
        return ""
    lookup = {_key(option): option for option in options}
    return lookup.get(_key(text), text)


def canonical_column(values: pd.Series, options: Iterable[str]) -> pd.Series:
    options = list(options)
    return values.map(lambda value: canonical(value, options))
