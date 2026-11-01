"""'Import from Excel' tab: upload a vendor Excel file, preview the MinerbaOne check, then import to the database."""
import pandas as pd
import streamlit as st

from core import material_groups, required
from core.schema import DB_COLS, pretty_label
from core.text_utils import normalize_name
from core.vendor_status import summarize
from repositories import vendor_repository
from services.excel_export import build_excel
from services.excel_import import ImportResult, parse_vendor_excel
from ui import state, theme
from ui.vendor_data import material_group_options
from ui.styles import build_vendor_column_config, style_rows, table_height, with_status_column

_MIME_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_MODE_APPEND = "Add to the vendors already in this list"
_MODE_REPLACE = "Replace every vendor in this list"


@st.cache_data(show_spinner=False)
def _parse_cached(data: bytes) -> ImportResult:
    return parse_vendor_excel(data)


def render(ctx: state.VendorContext) -> None:
    theme.steps(["Download the template (optional)", "Upload your Excel file", "Review & import"])

    info_col, template_col = st.columns([3, 1.3], vertical_alignment="center")
    info_col.caption(
        "Headers are recognised automatically — a single header row (e.g. `NIB NOMOR`) or the two-level company "
        "template both work. Each IUP holder is checked against MinerbaOne before anything is saved."
    )
    template_col.download_button(
        label="Empty template",
        icon=":material/download:",
        data=build_excel(pd.DataFrame(columns=DB_COLS), ctx.table),
        file_name="vendor_data_template.xlsx",
        mime=_MIME_XLSX,
        key="dl_template",
        width="stretch",
    )
    version = st.session_state.setdefault(state.KEY_EXCEL_UPLOAD_VER, 0)
    uploaded = st.file_uploader("Excel file (.xlsx)", type=["xlsx"], key=f"upload_{ctx.table}_{version}")
    if uploaded is None:
        return

    try:
        result = _parse_cached(uploaded.getvalue())
    except Exception as exc:  # noqa: BLE001 - a user file can be broken in many ways
        st.error(f"We couldn't read this file: {exc}", icon=":material/error:")
        return
    if result.data.empty:
        st.warning("No vendor rows found (the VENDOR and IUP holder columns are empty in every row).",
                   icon=":material/warning:")
        return
    _render_preview_and_import(ctx, result)


def _render_preview_and_import(ctx: state.VendorContext, result: ImportResult) -> None:
    data = result.data.copy()
    # same spelling as the dropdown, e.g. "batuan " -> "Batuan"
    data["golongan"] = material_groups.canonical_column(data["golongan"], material_group_options(ctx))
    checked = ctx.validate(data)
    s = summarize(checked)
    theme.kpi_cards([
        theme.Kpi("Rows read", theme.fmt_int(len(checked)), "from your file", theme.INDIGO),
        theme.Kpi("Verified", theme.fmt_int(s.verified), "found in MinerbaOne", theme.GREEN),
        theme.Kpi("Not found", theme.fmt_int(s.not_found), "check the IUP holder name", theme.RED),
    ])

    with st.expander("How your columns were matched", icon=":material/compare_arrows:"):
        st.write(", ".join(f"**{label}** → {pretty_label(db)}" for label, db in result.mapped))
        if result.unmapped:
            st.warning("These columns were not recognised and will be ignored: " + ", ".join(result.unmapped))
    st.dataframe(style_rows(with_status_column(checked)), width="stretch", height=table_height(len(checked), 300),
                 column_config=build_vendor_column_config(status_column=True))

    mode = st.radio("How should we import?", [_MODE_APPEND, _MODE_REPLACE], key=f"import_mode_{ctx.table}")
    replace = mode == _MODE_REPLACE
    to_save = checked
    if replace:
        st.warning(f"Every vendor currently in '{ctx.table}' will be replaced by the contents of this file.",
                   icon=":material/warning:")
    elif st.checkbox("Skip vendors that are already in the list (same vendor and IUP holder)", value=True,
                     key=f"skip_dup_{ctx.table}"):
        to_save, skipped = _drop_existing(checked, ctx.saved_df)
        if skipped:
            st.info(f"{skipped} row{'s' if skipped != 1 else ''} skipped because they already exist.",
                    icon=":material/info:")

    to_save, blocked = _check_required(ctx, to_save, replace)
    count = len(to_save)
    if st.button(f"Import {count} row{'s' if count != 1 else ''} into '{ctx.table}'", type="primary",
                 icon=":material/upload:", disabled=count == 0 or blocked, key="excel_import"):
        with st.spinner("Importing to the cloud database…"):
            records = vendor_repository.records_from_df(to_save, ctx.table)
            vendor_repository.save_records(records, ctx.table, replace=replace)
        st.session_state[state.KEY_EXCEL_UPLOAD_VER] += 1
        state.invalidate_vendor_data()
        state.set_flash(f"Imported {len(records)} row{'s' if len(records) != 1 else ''} into the list '{ctx.table}'.")
        st.rerun()


def _check_required(ctx: state.VendorContext, to_save: pd.DataFrame, replace: bool):
    """
    New records need the required fields. Append: incomplete rows are left out (and listed).
    Replace: rows that are new to the list must be complete, otherwise the import is blocked
    (leaving them out would delete them). Returns (rows to import, blocked).
    """
    checked = required.new_rows(to_save, ctx.saved_df) if replace else to_save
    incomplete = required.incomplete_rows(checked)
    if incomplete.empty:
        return to_save, False
    count = len(incomplete)
    rows_text = f"{count} row{'s' if count != 1 else ''}"
    if replace:
        st.error(f"{rows_text} in the file {'are' if count != 1 else 'is'} missing required fields. Every new "
                 f"record needs {required.required_text()}. Fill them in the Excel file and upload it again.",
                 icon=":material/assignment_late:")
    else:
        st.warning(f"{rows_text} will be left out because {'they are' if count != 1 else 'it is'} missing "
                   f"required fields ({required.required_text()}). Fill them in the Excel file and upload again "
                   "to include them.", icon=":material/assignment_late:")
    st.dataframe(
        pd.DataFrame({
            "Missing": incomplete[required.MISSING_COLUMN], "Holder Name": incomplete["iup_nama"],
            "Vendor": incomplete["vendor"], "PIC": incomplete["nama_pic"], "Material Group": incomplete["golongan"],
        }, index=incomplete.index),
        width="stretch", height=min(320, 40 + 35 * count),
    )
    if replace:
        return to_save, True
    return to_save.drop(index=incomplete.index), False


def _row_keys(df: pd.DataFrame):
    return [(normalize_name(v), normalize_name(i)) for v, i in zip(df["vendor"], df["iup_nama"])]


def _drop_existing(new_rows: pd.DataFrame, saved: pd.DataFrame):
    """Drop rows whose VENDOR & IUP holder already exist in the saved data. Returns (remaining, skipped count)."""
    existing = set(_row_keys(saved))
    keep = [key not in existing for key in _row_keys(new_rows)]
    return new_rows[keep], len(keep) - sum(keep)
