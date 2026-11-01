"""'Monthly price & density' block inside the details popup.

Holder view: one column per vendor that uses the holder. Vendor view: one column per holder the vendor uses.
Rows are months: a past year shows all 12, the current year shows January up to last month.
"""
from datetime import date
from typing import Dict, List, Mapping

import pandas as pd
import streamlit as st

from core import monthly
from repositories import monthly_repository
from ui import state, theme

_KEY_READY = "monthly_table_ok"
_KEY_ROWS = "monthly_rows"        # {list name: [records]}, cleared after a save
_KEY_VER = "monthly_editor_ver"

_FIELD_INFO = {
    monthly.FIELD_PRICE: dict(
        title="Price per MT (Rp)", unit="Rp", fmt="localized", step=1.0,
        help="Price per metric ton for the month, in rupiah.",
    ),
    monthly.FIELD_DENSITY: dict(
        title="Density (t/m³)", unit="t/m³", fmt="%.3f", step=0.001,
        help="Material density for the month (ton per cubic metre). Use it to monitor material quality.",
    ),
}


def render(ctx: state.VendorContext, view: str, own_key: str, own_name: str, counterparts: Mapping[str, str]) -> None:
    """
    view: "holder" (columns = vendors) or "vendor" (columns = holders).
    own_key / own_name: the holder (or vendor) shown in the popup. counterparts: {normalized key: display name}.
    """
    theme.detail_title("Monthly price & density")
    if not _table_ready():
        return
    if not counterparts:
        st.caption("No vendor recorded for this holder yet." if view == "holder"
                   else "No IUP holder recorded for this vendor yet.")
        return

    records = _records(ctx.table)
    years = monthly.year_options((r.get("year") for r in records))
    today = date.today()
    default_year = today.year if monthly.visible_months(today.year, today) else today.year - 1
    year = st.selectbox("Year", years, index=years.index(default_year), key=f"monthly_year_{view}_{own_key}",
                        help="A past year shows all 12 months. This year shows January up to last month.")
    months = monthly.visible_months(year, today)
    if not months:
        st.info("No finished month in this year yet. Pick last year to see or enter data.", icon=":material/event:")
        return

    if view == "holder":
        axis_key, fixed, per = monthly.VENDOR_KEY, {monthly.HOLDER_KEY: own_key}, "vendor"
    else:
        axis_key, fixed, per = monthly.HOLDER_KEY, {monthly.VENDOR_KEY: own_key}, "IUP holder"
    names = {**counterparts, own_key: own_name}
    span = f"{monthly.MONTH_NAMES[months[0] - 1]}–{monthly.MONTH_NAMES[months[-1] - 1]} {year}"
    st.caption(f"{span} · one column per {per}. Click a cell to type a value, then press Save.")

    for field in monthly.FIELDS:
        _field_grid(ctx, records, field, axis_key, counterparts, fixed, names, year, months, view, own_key)


# ------------------------------------------------------------------ data
def _table_ready() -> bool:
    if not st.session_state.get(_KEY_READY):
        st.session_state[_KEY_READY] = monthly_repository.table_ready()
    if st.session_state[_KEY_READY]:
        return True
    st.info("Monthly prices and densities need a new table in Supabase. Open Supabase → SQL Editor, "
            "run the SQL below once, then click the button.", icon=":material/database:")
    st.code(monthly_repository.MIGRATION_SQL, language="sql")
    if st.button("I ran it, check again", icon=":material/refresh:", key="monthly_check_again"):
        st.session_state.pop(_KEY_READY, None)
        st.rerun(scope="fragment")
    return False


def _records(table: str) -> List[dict]:
    cache = st.session_state.setdefault(_KEY_ROWS, {})
    if table not in cache:
        cache[table] = monthly_repository.fetch(table)
    return cache[table]


def _invalidate(table: str) -> None:
    st.session_state.get(_KEY_ROWS, {}).pop(table, None)
    st.session_state[_KEY_VER] = st.session_state.get(_KEY_VER, 0) + 1


# ------------------------------------------------------------------ one grid (price or density)
def _field_grid(ctx: state.VendorContext, records: List[dict], field: str, axis_key: str,
                columns: Mapping[str, str], fixed: Dict[str, str], names: Mapping[str, str],
                year: int, months: List[int], view: str, own_key: str) -> None:
    info = _FIELD_INFO[field]
    grid = monthly.build_grid(records, field, axis_key, columns, fixed, year, months)
    version = st.session_state.get(_KEY_VER, 0)
    with st.form(f"monthly_form_{field}_{view}_{own_key}_{year}_{version}", border=True):
        st.markdown(f"**{info['title']}**")
        edited = st.data_editor(
            grid, num_rows="fixed", width="stretch", height=40 + 35 * len(months),
            column_config={
                label: st.column_config.NumberColumn(label, min_value=0.0, step=info["step"], format=info["fmt"],
                                                     help=info["help"])
                for label in grid.columns
            },
            key=f"monthly_editor_{field}_{view}_{own_key}_{year}_{version}",
        )
        _averages_caption(grid, info["unit"], field)
        saved = st.form_submit_button(f"Save {info['title'].split(' (')[0].lower()}", icon=":material/save:",
                                      type="primary")
    if not saved:
        return
    changes = monthly.grid_changes(grid, edited, field, axis_key, columns, fixed, names, year)
    if not changes:
        st.toast("Nothing changed.", icon="ℹ️")
        return
    try:
        with st.spinner("Saving…"):
            monthly_repository.upsert(changes, ctx.table)
    except Exception as exc:  # noqa: BLE001 - show a readable message instead of a crash
        st.error(f"Could not save: {exc}", icon=":material/cloud_off:")
        return
    _invalidate(ctx.table)
    st.toast(f"Saved {len(changes)} value{'s' if len(changes) != 1 else ''}.", icon="✅")
    st.rerun(scope="fragment")


def _averages_caption(grid: pd.DataFrame, unit: str, field: str) -> None:
    averages = monthly.column_averages(grid)
    if not averages:
        st.caption("No values for this year yet.")
        return
    if field == monthly.FIELD_PRICE:
        parts = [f"{name}: Rp {value:,.0f}" for name, value in averages.items()]
    else:
        parts = [f"{name}: {value:.3f} {unit}" for name, value in averages.items()]
    st.caption("Average of filled months — " + " · ".join(parts))
