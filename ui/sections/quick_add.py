"""'Add vendor' popup: one short form with every field, a duplicate check, then save (no table scrolling)."""
from datetime import date
from typing import Dict

import pandas as pd
import streamlit as st

from core import duplicates, material_groups, required
from core.schema import DATE_COLS
from core.text_utils import to_int_str
from core.vendor_status import STATUS_LABELS, row_status
from ui import state, theme
from ui.vendor_data import add_record, current_saved, material_group_options, remember_new_group

# (section title, [(column, label, placeholder / help)]). Dates use a date picker.
_FORM = (
    ("Vendor & contact", [
        ("vendor", "Vendor *", "Company that supplies the material"),
        ("nama_pic", "PIC name *", "Person in charge at the vendor"),
        ("no_kontak", "Contact no.", "0812… or 62812… (becomes a WhatsApp link)"),
        ("golongan", "Material group *", "Choose a group, or type a new one if none fits"),
        ("nib_lokasi", "Allocation", "Where the material is allocated"),
    ]),
    ("IUP (mining business permit)", [
        ("iup_nama", "IUP holder name *", "Checked against MinerbaOne automatically"),
        ("iup_nomor", "IUP number", "Filled from MinerbaOne when found"),
        ("iup_bentuk_usaha", "Entity type", "e.g. IUP Operasi Produksi"),
        ("iup_tanggal_terbit", "Issue date", ""),
        ("iup_periode", "Term (years)", "e.g. 5"),
        ("iup_tanggal_berakhir", "Expiry date", ""),
    ]),
    ("NIB (business ID number)", [
        ("nib_nomor", "NIB number", "13 digits"),
        ("nib_tanggal", "NIB date", ""),
    ]),
    ("Support letter", [
        ("surat_dukungan_nomor", "Letter number", ""),
        ("surat_dukungan_tanggal", "Letter date", ""),
        ("surat_dukungan_lokasi_quarry", "Quarry location", "Village / district of the quarry"),
    ]),
    ("Location & notes", [
        ("lokasi_maps", "Google Maps link", "https://maps.app.goo.gl/…"),
        ("smart_comp", "Smart Comp", "Smart Comp check result"),
        ("remark", "Remark", "Your notes"),
    ]),
)
_FIELD_KEY = "qa_{}_{}"   # widget key: version, column


def _version() -> int:
    return st.session_state.setdefault("quick_add_ver", 0)


@st.dialog("Add a vendor record", width="medium")
def show(ctx: state.VendorContext) -> None:
    st.caption(f"Saved to the list **{ctx.table}**. Fields marked * are required ({required.required_text()}). "
               "MinerbaOne status, IUP details and the countdown are filled in automatically.")
    version = _version()
    groups = material_group_options(ctx)
    with st.form(f"quick_add_form_{version}", border=False):
        for title, fields in _FORM:
            theme.detail_title(title)
            left, right = st.columns(2)
            for i, (column, label, hint) in enumerate(fields):
                with left if i % 2 == 0 else right:
                    _field(version, column, label, hint, groups)
        submitted = st.form_submit_button("Check & save", type="primary", icon=":material/save:", width="stretch")

    if submitted:
        values = _collect(version, groups)
        error = _check(values)
        if error:
            st.error(error, icon=":material/error:")
            return
        related = duplicates.find_related(current_saved(ctx), values["vendor"], values["iup_nama"])
        if related.empty:
            _save(ctx, values)
            return
        st.session_state[state.KEY_ADD_PENDING] = values

    pending = st.session_state.get(state.KEY_ADD_PENDING)
    if pending:
        _duplicate_panel(ctx, pending)


def _field(version: int, column: str, label: str, hint: str, groups) -> None:
    key = _FIELD_KEY.format(version, column)
    if column == "golongan":
        st.selectbox(label, groups, index=None, key=key, placeholder="Choose a material group",
                     accept_new_options=True, help=hint + ". A new group is added to the list once you save.")
    elif column in DATE_COLS:
        st.date_input(label, value=None, key=key, format="DD/MM/YYYY",
                      min_value=date(1990, 1, 1), max_value=date(2100, 12, 31))
    else:
        st.text_input(label, key=key, placeholder=hint)


def _collect(version: int, groups) -> Dict[str, str]:
    values = {}
    for _, fields in _FORM:
        for column, _, _ in fields:
            raw = st.session_state.get(_FIELD_KEY.format(version, column))
            if isinstance(raw, date):
                values[column] = raw.isoformat()
            else:
                values[column] = str(raw or "").strip()
    values["golongan"] = material_groups.canonical(values["golongan"], groups)
    if values.get("iup_periode"):
        values["iup_periode"] = str(to_int_str(values["iup_periode"]))
    return values


def _check(values: Dict[str, str]) -> str:
    missing = required.missing_fields(values)
    if missing:
        return "Please fill in: " + ", ".join(missing) + "."
    if values["iup_periode"] and not values["iup_periode"].lstrip("-").isdigit():
        return "Term (years) must be a number, e.g. 5."
    maps = values["lokasi_maps"]
    if maps and not maps.lower().startswith(("http://", "https://")):
        return "The Google Maps link must start with https://"
    return ""


def _duplicate_panel(ctx: state.VendorContext, values: Dict[str, str]) -> None:
    related = duplicates.find_related(current_saved(ctx), values["vendor"], values["iup_nama"])
    if related.empty:  # the saved data changed meanwhile
        st.session_state.pop(state.KEY_ADD_PENDING, None)
        return
    st.warning(
        f"Found **{len(related)}** saved record{'s' if len(related) != 1 else ''} with the same or a similar "
        "vendor / IUP holder. Check them so you don't add the same data twice.",
        icon=":material/content_copy:",
    )
    st.dataframe(_related_table(related), width="stretch", hide_index=False,
                 height=min(320, 40 + 35 * len(related)),
                 column_config={"_index": st.column_config.TextColumn("No", width=55)})
    save_col, back_col = st.columns(2)
    if save_col.button("Save anyway", type="primary", icon=":material/save:", width="stretch", key="qa_save_anyway"):
        _save(ctx, values)
    if back_col.button("Don't save", icon=":material/close:", width="stretch", key="qa_cancel"):
        st.session_state.pop(state.KEY_ADD_PENDING, None)
        st.rerun(scope="fragment")


def _related_table(related: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({
        "Match": related[duplicates.MATCH_COLUMN],
        "Holder Name": related["iup_nama"],
        "Vendor": related["vendor"],
        "PIC": related["nama_pic"],
        "Contact": related["no_kontak"],
        "Status": row_status(related).map(STATUS_LABELS),
    }, index=related.index)


def _save(ctx: state.VendorContext, values: Dict[str, str]) -> None:
    add_record(ctx, values)
    remember_new_group(ctx, values["golongan"])
    st.session_state.pop(state.KEY_ADD_PENDING, None)
    st.session_state["quick_add_ver"] = _version() + 1   # fresh, empty form next time
    name = values["iup_nama"] or values["vendor"]
    state.set_flash(f"Added '{name}' to the list '{ctx.table}'.")
    st.rerun()
