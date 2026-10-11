"""Panel pengaturan pencocokan nama & pengisian otomatis dari data ESDM."""
import pandas as pd
import streamlit as st

from core.schema import pretty_label
from core.validation import (
    MINERBA_FIELDS,
    ValidationSettings,
    default_field_map,
    default_match_column,
)

_NOT_FILLED = "(tidak diisi)"


def render(df_minerba: pd.DataFrame) -> ValidationSettings:
    columns = list(df_minerba.columns)
    with st.expander("⚙️ Pengaturan pencocokan & pengisian otomatis", expanded=False):
        threshold = st.slider(
            "Tingkat kemiripan nama (%)", min_value=50, max_value=100, value=80,
            help="100 = nama harus sama persis (abaikan PT/CV & tanda baca). "
                 "Turunkan jika ingin toleransi typo kecil.",
        )
        warn_days = st.slider(
            "Beri peringatan di Remark jika IUP berakhir dalam (hari)",
            min_value=30, max_value=730, value=180,
        )
        match_col = _select_match_column(columns)
        field_map = _select_field_map(columns)
    return ValidationSettings(threshold=threshold, warn_days=warn_days, match_col=match_col, field_map=field_map)


def _select_match_column(columns):
    if not columns:
        return None
    default = default_match_column(columns)
    return st.selectbox(
        "Kolom ESDM yang dicocokkan dengan IUP NAMA (vendor)",
        columns,
        index=columns.index(default) if default in columns else 0,
        key="match_col",
    )


def _select_field_map(columns):
    st.markdown("**Kolom ESDM yang mengisi kolom vendor** (otomatis terdeteksi, bisa diubah)")
    options = [_NOT_FILLED] + columns
    detected = default_field_map(columns)
    field_map = {}
    grid = st.columns(3)
    for n, target in enumerate(MINERBA_FIELDS):
        default = detected[target]
        choice = grid[n % 3].selectbox(
            pretty_label(target), options,
            index=options.index(default) if default in options else 0,
            key=f"map_{target}",
        )
        field_map[target] = None if choice == _NOT_FILLED else choice

    missing = [pretty_label(t) for t, col in field_map.items() if col is None]
    if missing and columns:
        st.warning(
            f"Kolom ESDM belum terpilih untuk: {', '.join(missing)} — kolom ini tidak akan terisi otomatis. "
            f"Pilih manual di atas. Kolom yang tersedia di tabel ESDM: {', '.join(columns)}"
        )
    return field_map
