"""'Matching rules' popover: how vendor names are matched to the ESDM data and which columns get auto-filled."""
import pandas as pd
import streamlit as st

from core.schema import pretty_label
from core.validation import (
    MINERBA_FIELDS,
    ValidationSettings,
    default_field_map,
    default_match_column,
)
from ui.styles import minerba_label

_NOT_FILLED = "(don't fill)"


def render(df_minerba: pd.DataFrame) -> ValidationSettings:
    columns = list(df_minerba.columns)
    with st.popover("Matching rules", icon=":material/tune:", width="stretch"):
        st.markdown("**Matching rules**")
        st.caption("How vendors are checked against MinerbaOne. The defaults work for most cases.")
        threshold = st.slider(
            "Name similarity required", min_value=50, max_value=100, value=80, format="%d%%", key="match_threshold",
            help="100% = the names must match exactly (PT/CV and punctuation are ignored). "
                 "Lower it to tolerate small typos.",
        )
        warn_days = st.slider(
            "Warn when the IUP expires within", min_value=30, max_value=730, value=180, format="%d days",
            key="warn_days",
        )
        match_col = _select_match_column(columns)
        field_map = _select_field_map(columns)
    return ValidationSettings(threshold=threshold, warn_days=warn_days, match_col=match_col, field_map=field_map)


def _select_match_column(columns):
    if not columns:
        return None
    default = default_match_column(columns)
    return st.selectbox(
        "MinerbaOne column compared with the IUP holder name",
        columns,
        index=columns.index(default) if default in columns else 0,
        format_func=minerba_label,
        key="match_col",
    )


def _select_field_map(columns):
    st.markdown("**Auto-filled fields**")
    st.caption("When a vendor is found, these fields are copied from MinerbaOne (detected automatically).")
    options = [_NOT_FILLED] + columns
    detected = default_field_map(columns)
    field_map = {}
    grid = st.columns(2)
    for n, target in enumerate(MINERBA_FIELDS):
        default = detected[target]
        choice = grid[n % 2].selectbox(
            pretty_label(target), options,
            index=options.index(default) if default in options else 0,
            format_func=lambda c: c if c == _NOT_FILLED else minerba_label(c),
            key=f"map_{target}",
        )
        field_map[target] = None if choice == _NOT_FILLED else choice

    missing = [pretty_label(t) for t, col in field_map.items() if col is None]
    if missing and columns:
        st.caption(f"Not auto-filled (no matching MinerbaOne column): {', '.join(missing)}. "
                   "Type these in by hand, or pick a column above.")
    return field_map
