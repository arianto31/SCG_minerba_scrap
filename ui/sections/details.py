"""Details popup opened by clicking a Holder Name or Vendor cell in the vendor table.

- Holder view: every column of the clicked record, Google Maps location, IUP renewal tracker (when the holder
  is not verified), and the PICs that use this holder.
- Vendor view: the vendor's details and every holder it manages, each with its map link.
Both views can switch to each other inside the same popup (with a Back button).
"""
from datetime import date
from typing import List
from urllib.parse import quote_plus

import pandas as pd
import streamlit as st

from core import renewal
from core.phone import to_whatsapp_url
from core.schema import RENEWAL_COL, VALID_MANUAL
from core.text_utils import is_blank, normalize_name, parse_date
from core.vendor_status import (
    STATUS_ATTENTION, STATUS_INCOMPLETE, STATUS_NOT_FOUND, STATUS_VERIFIED, row_status,
)
from ui import state, theme
from ui.sections import monthly as monthly_section
from ui.vendor_data import current_saved, update_holder

KIND_HOLDER = "holder"
KIND_VENDOR = "vendor"

_STATUS_BADGE = {
    STATUS_VERIFIED: ("Verified", theme.GREEN),
    STATUS_NOT_FOUND: ("Not found in MinerbaOne", theme.RED),
    STATUS_ATTENTION: ("Needs attention", theme.AMBER),
    STATUS_INCOMPLETE: ("No IUP holder name", theme.SLATE),
}


# ------------------------------------------------------------------ open / navigate
def open_details(kind: str, df: pd.DataFrame, label) -> bool:
    """Remember what to show (from a clicked table cell). False when the clicked cell is empty."""
    column = "iup_nama" if kind == KIND_HOLDER else "vendor"
    key = normalize_name(df.at[label, column])
    if not key:
        return False
    st.session_state[state.KEY_DETAIL] = {"kind": kind, "key": key, "row": label, "history": []}
    return True


def _go(kind: str, key: str, row=None) -> None:
    """Button callback: switch view inside the popup, keeping a history for Back."""
    current = st.session_state.get(state.KEY_DETAIL) or {}
    history = list(current.get("history", []))
    if current:
        history.append({k: current.get(k) for k in ("kind", "key", "row")})
    st.session_state[state.KEY_DETAIL] = {"kind": kind, "key": key, "row": row, "history": history[-10:]}


def _back() -> None:
    current = st.session_state.get(state.KEY_DETAIL) or {}
    history = list(current.get("history", []))
    if history:
        previous = history.pop()
        st.session_state[state.KEY_DETAIL] = {**previous, "history": history}


@st.dialog("Details", width="medium", on_dismiss="rerun")
def show(ctx: state.VendorContext) -> None:
    """The popup. Re-reads the saved data each time, so changes made inside it show at once."""
    target = st.session_state.get(state.KEY_DETAIL)
    if not target:
        st.info("Nothing selected.")
        return
    df = current_saved(ctx)
    if target.get("history"):
        st.button("Back", icon=":material/arrow_back:", type="tertiary", on_click=_back, key="detail_back")
    if target["kind"] == KIND_HOLDER:
        _holder_view(ctx, df, target)
    else:
        _vendor_view(ctx, df, target)


# ------------------------------------------------------------------ formatting helpers
def _text(value) -> str:
    return "" if is_blank(value) else str(value).strip()


def _fmt_date(value) -> str:
    parsed = parse_date(value)
    return parsed.strftime("%d %b %Y") if pd.notna(parsed) else _text(value)


def _fmt_days(value) -> str:
    try:
        days = int(float(str(value)))
    except (TypeError, ValueError):
        return ""
    if days < 0:
        return f"Expired {abs(days):,} day{'s' if abs(days) != 1 else ''} ago"
    return f"{days:,} day{'s' if days != 1 else ''} left"


def _fmt_stamp(stamp: str) -> str:
    if not stamp:
        return ""
    days = renewal.days_since(stamp)
    try:
        shown = pd.Timestamp(stamp).strftime("%d %b %Y, %H:%M")
    except (TypeError, ValueError):
        shown = stamp
    if days is None:
        return shown
    ago = "today" if days == 0 else "yesterday" if days == 1 else f"{days} days ago"
    return f"{shown} ({ago})"


def _contact_html(value) -> str:
    text = _text(value)
    url = to_whatsapp_url(text)
    return theme.link(url, f"{text}  ·  WhatsApp ↗") if url else ""


def _maps_link(rows: pd.DataFrame) -> str:
    """First Google Maps link stored on any row of this holder."""
    for value in rows.get("lokasi_maps", pd.Series(dtype=object)):
        if _text(value):
            return _text(value)
    return ""


def _maps_search_url(row: pd.Series) -> str:
    place = _text(row.get("surat_dukungan_lokasi_quarry"))
    if not place:
        return ""
    return f"https://www.google.com/maps/search/?api=1&query={quote_plus(place)}"


def _status_badge(status: str) -> str:
    text, color = _STATUS_BADGE[status]
    return theme.badge(text, color)


def _people(rows: pd.DataFrame) -> List[theme.Person]:
    """One entry per distinct PIC (+ vendor + contact)."""
    seen, people = set(), []
    for _, row in rows.iterrows():
        pic, vendor, contact = _text(row["nama_pic"]), _text(row["vendor"]), _text(row["no_kontak"])
        key = (normalize_name(pic), normalize_name(vendor), contact)
        if key in seen or not (pic or contact):
            continue
        seen.add(key)
        sub = " · ".join(part for part in (vendor, _text(row["golongan"])) if part)
        people.append(theme.Person(pic or "Unnamed PIC", sub, to_whatsapp_url(contact) or "", contact))
    return people


# ------------------------------------------------------------------ holder view
def _holder_view(ctx: state.VendorContext, df: pd.DataFrame, target: dict) -> None:
    key = target["key"]
    rows = df[df["iup_nama"].map(normalize_name) == key]
    if rows.empty:
        st.info("This IUP holder is no longer in the saved list.", icon=":material/info:")
        return
    label = target.get("row") if target.get("row") in rows.index else rows.index[0]
    row = rows.loc[label]
    status = row_status(rows.loc[[label]]).iloc[0]
    tracker, from_remark = renewal.for_rows(rows[RENEWAL_COL] if RENEWAL_COL in rows else [], rows["remark"])

    vendors = list(dict.fromkeys(_text(v) for v in rows["vendor"] if _text(v)))
    badges = [_status_badge(status)]
    days = _fmt_days(row["iup_countdown"])
    if days:
        badges.append(theme.badge(days, theme.RED if days.startswith("Expired") else theme.CYAN))
    if row["minerbaone"] == VALID_MANUAL:
        badges.append(theme.badge("Verified by hand", theme.INDIGO))
    if renewal.is_stale(tracker):
        badges.append(theme.badge("Renewal: no recent update", theme.AMBER))
    theme.detail_header(
        "IUP holder", _text(row["iup_nama"]),
        f"Record No. {label} in '{ctx.table}' · used by {len(vendors)} vendor{'s' if len(vendors) != 1 else ''}",
        badges,
    )
    _vendor_links(vendors, key)

    # 1) every column of the clicked record, grouped
    _record_cards(row)
    # 2) location
    _location_section(ctx, key, rows, row)
    # 3) monthly price per MT (per vendor) and density
    monthly_section.render(ctx, "holder", key, _text(row["iup_nama"]),
                           {normalize_name(v): v for v in vendors})
    # 4) renewal tracker (holders that are not verified, or that have a tracker)
    if status in (STATUS_NOT_FOUND, STATUS_ATTENTION) or not tracker.is_empty:
        _renewal_section(ctx, key, status, tracker, row, from_remark)
    # 5) PICs using this holder
    theme.people_card(f"PICs using this holder ({len(_people(rows))})", _people(rows),
                      "No PIC recorded for this holder yet.")


def _vendor_links(vendors: List[str], holder_key: str) -> None:
    if not vendors:
        return
    st.caption("Managed by — click to open the vendor:")
    with st.container(horizontal=True, gap="small"):
        for i, vendor in enumerate(vendors):
            st.button(vendor, icon=":material/storefront:", key=f"to_vendor_{holder_key}_{i}",
                      on_click=_go, args=(KIND_VENDOR, normalize_name(vendor)))


def _record_cards(row: pd.Series) -> None:
    theme.detail_card("Vendor & contact", [
        theme.Field("Vendor", _text(row["vendor"])),
        theme.Field("PIC name", _text(row["nama_pic"])),
        theme.Field("Contact no.", _text(row["no_kontak"]), html=_contact_html(row["no_kontak"])),
        theme.Field("Material group", _text(row["golongan"])),
        theme.Field("Allocation", _text(row["nib_lokasi"])),
    ])
    theme.detail_card("IUP (mining business permit)", [
        theme.Field("Holder name", _text(row["iup_nama"])),
        theme.Field("IUP number", _text(row["iup_nomor"])),
        theme.Field("Entity type", _text(row["iup_bentuk_usaha"])),
        theme.Field("Issue date", _fmt_date(row["iup_tanggal_terbit"])),
        theme.Field("Term (years)", _text(row["iup_periode"])),
        theme.Field("Expiry date", _fmt_date(row["iup_tanggal_berakhir"])),
        theme.Field("Days left", _fmt_days(row["iup_countdown"])),
    ])
    theme.detail_card("Verification", [
        theme.Field("MinerbaOne", _text(row["minerbaone"])),
        theme.Field("Smart Comp", _text(row["smart_comp"])),
        theme.Field("Remark", _text(row["remark"])),
    ])
    theme.detail_card("NIB (business ID number)", [
        theme.Field("NIB number", _text(row["nib_nomor"])),
        theme.Field("NIB date", _fmt_date(row["nib_tanggal"])),
    ])
    theme.detail_card("Support letter", [
        theme.Field("Letter number", _text(row["surat_dukungan_nomor"])),
        theme.Field("Letter date", _fmt_date(row["surat_dukungan_tanggal"])),
        theme.Field("Quarry location", _text(row["surat_dukungan_lokasi_quarry"])),
    ])


def _location_section(ctx: state.VendorContext, key: str, rows: pd.DataFrame, row: pd.Series) -> None:
    maps = _maps_link(rows)
    theme.detail_card("Location", [
        theme.Field("Google Maps", html=theme.link(maps, "Open in Google Maps ↗") if maps else ""),
        theme.Field("Quarry location", _text(row["surat_dukungan_lokasi_quarry"])),
    ])
    if maps:
        container = st.expander("Change the Google Maps link", icon=":material/edit_location_alt:")
    else:
        container = st.container()
    with container:
        with st.form(f"maps_form_{key}", border=False):
            url = st.text_input(
                "Google Maps link", value=maps, placeholder="Paste a link, e.g. https://maps.app.goo.gl/…",
                help="Open the place in Google Maps, press Share → Copy link, and paste it here. "
                     "Saved for every record of this holder.",
            )
            submitted = st.form_submit_button("Save location", icon=":material/save:", type="primary")
        search = _maps_search_url(row)
        if search and not maps:
            st.link_button("Find the quarry location on Google Maps", search, icon=":material/travel_explore:")
    if submitted:
        url = url.strip()
        if url and not url.lower().startswith(("http://", "https://")):
            st.error("Please paste a full link that starts with https://", icon=":material/link_off:")
            return
        if url == maps:
            st.toast("The location did not change.", icon="ℹ️")
            return
        update_holder(ctx, key, {"lokasi_maps": url})
        st.toast("Location saved." if url else "Location removed.", icon="✅")
        st.rerun(scope="fragment")


# ------------------------------------------------------------------ IUP renewal tracker
def _renewal_section(ctx: state.VendorContext, key: str, status: str, tracker: renewal.Renewal,
                     row: pd.Series, from_remark: bool = False) -> None:
    theme.detail_title("IUP renewal tracker")
    if from_remark:
        st.caption("Steps read from the remark (“1. Step; updated on YYYY-MM-DD”). "
                   "Click **Save progress** to keep them in the tracker.")
    if tracker.is_verified and status == STATUS_VERIFIED:
        _verified_summary(ctx, key, tracker)
        return

    last = tracker.last_update
    theme.progress(tracker.done_count, tracker.total,
                   f"{tracker.done_count} of {tracker.total} steps done",
                   f"Last update: {_fmt_stamp(last)}" if last else "Not started yet")
    if renewal.is_stale(tracker):
        st.warning(f"No progress for {renewal.days_since(last)} days. Follow up with the vendor on the next step.",
                   icon=":material/schedule:")
    elif status == STATUS_ATTENTION and tracker.is_empty:
        st.info("This IUP expires soon. Track the extension here step by step.", icon=":material/info:")
    elif status == STATUS_NOT_FOUND and tracker.is_empty:
        st.info("This holder is not found in MinerbaOne. If the IUP is being renewed, track it here; "
                "otherwise check the spelling of the holder name.", icon=":material/info:")
    if tracker.is_verified:
        st.caption(f"Previous renewal verified on {_fmt_stamp(tracker.verified_on)}.")

    version = tracker.last_update or "new"
    with st.form(f"renewal_form_{key}", border=False):
        done, notes = [], []
        for i, (title, description) in enumerate(renewal.RENEWAL_STEPS):
            step = tracker.steps[i]
            with st.container(border=True):
                done.append(st.checkbox(f"**{i + 1}. {title}**", value=step.done, key=f"rn_done_{key}_{i}_{version}"))
                when = f"Last updated {_fmt_stamp(step.updated)}" if step.updated else "No update yet"
                st.caption(f"{description}  \n{when}")
                notes.append(st.text_input(
                    f"Note for step {i + 1}", value=step.note, key=f"rn_note_{key}_{i}_{version}",
                    placeholder="Optional note, e.g. submitted on 12 Oct, waiting for review",
                    label_visibility="collapsed",
                ))
        saved = st.form_submit_button("Save progress", icon=":material/save:", type="primary")
    if saved:
        updated = renewal.update_steps(tracker, done, notes)
        if updated == tracker and not from_remark:
            st.toast("Nothing changed.", icon="ℹ️")
        else:
            update_holder(ctx, key, {RENEWAL_COL: renewal.dump(updated)})
            st.toast("Renewal progress saved.", icon="✅")
            st.rerun(scope="fragment")

    _verify_form(ctx, key, status, tracker, row)


def _verify_form(ctx: state.VendorContext, key: str, status: str, tracker: renewal.Renewal, row: pd.Series) -> None:
    if not tracker.all_done:
        st.button("Mark as verified", icon=":material/verified:", disabled=True, key=f"verify_locked_{key}",
                  help=f"Finish all {tracker.total} steps (and save) first.")
        return
    st.success("All steps are done. Enter the new IUP details, then mark the holder as verified.",
               icon=":material/task_alt:")
    current_end = parse_date(row["iup_tanggal_berakhir"])
    with st.form(f"verify_form_{key}", border=True):
        new_end = st.date_input(
            "New IUP expiry date" + (" (required)" if status == STATUS_ATTENTION else ""),
            value=None, format="DD/MM/YYYY", min_value=date(2000, 1, 1), max_value=date(2100, 12, 31),
            help="From the new IUP decree. The countdown and warnings use this date.",
        )
        new_number = st.text_input("New IUP number (optional)", placeholder="Number on the new decree")
        go = st.form_submit_button("Mark as verified", icon=":material/verified:", type="primary")
    if not go:
        return
    if status == STATUS_ATTENTION and new_end is None:
        st.error("Enter the new IUP expiry date — the current one is expiring.", icon=":material/event_busy:")
        return
    if new_end is not None and pd.notna(current_end) and pd.Timestamp(new_end) <= current_end:
        st.error(f"The new expiry date must be later than the current one ({_fmt_date(current_end)}).",
                 icon=":material/event_busy:")
        return
    iso = new_end.isoformat() if new_end else ""
    updates = {RENEWAL_COL: renewal.dump(renewal.mark_verified(tracker, iso, new_number))}
    if iso:
        updates["iup_tanggal_berakhir"] = iso
    if new_number.strip():
        updates["iup_nomor"] = new_number.strip()
    result = update_holder(ctx, key, updates)
    new_status = row_status(result[result["iup_nama"].map(normalize_name) == key]).iloc[0]
    if new_status == STATUS_VERIFIED:
        st.toast("Holder marked as verified.", icon="✅")
    else:
        st.toast("Saved, but the IUP still needs attention — check the new expiry date.", icon="⚠️")
    st.rerun(scope="fragment")


def _verified_summary(ctx: state.VendorContext, key: str, tracker: renewal.Renewal) -> None:
    lines = [f"Renewal completed and verified on **{_fmt_stamp(tracker.verified_on)}**."]
    if tracker.renewed_until:
        lines.append(f"New expiry date: **{_fmt_date(tracker.renewed_until)}**.")
    if tracker.new_iup_number:
        lines.append(f"New IUP number: **{tracker.new_iup_number}**.")
    st.success("  \n".join(lines), icon=":material/verified:")
    with st.expander("Undo the verification", icon=":material/undo:"):
        st.caption("Use this if the holder was verified by mistake. The steps stay ticked; "
                   "a manually entered expiry date stays until you change it in the table.")
        if st.button("Undo verification", key=f"undo_verify_{key}"):
            undone = renewal.Renewal(steps=tracker.steps)
            update_holder(ctx, key, {RENEWAL_COL: renewal.dump(undone)})
            st.toast("Verification undone.", icon="↩️")
            st.rerun(scope="fragment")


# ------------------------------------------------------------------ vendor view
def _vendor_view(ctx: state.VendorContext, df: pd.DataFrame, target: dict) -> None:
    key = target["key"]
    rows = df[df["vendor"].map(normalize_name) == key]
    if rows.empty:
        st.info("This vendor is no longer in the saved list.", icon=":material/info:")
        return
    statuses = row_status(rows)
    name = next((_text(v) for v in rows["vendor"] if _text(v)), key)
    holder_keys = [k for k in dict.fromkeys(rows["iup_nama"].map(normalize_name)) if k]

    badges = []
    for status in (STATUS_VERIFIED, STATUS_ATTENTION, STATUS_NOT_FOUND):
        count = int((statuses == status).sum())
        if count:
            text, color = _STATUS_BADGE[status]
            badges.append(theme.badge(f"{count} {text.lower()}", color))
    theme.detail_header("Vendor", name,
                        f"Manages {len(holder_keys)} IUP holder{'s' if len(holder_keys) != 1 else ''} · "
                        f"{len(rows)} record{'s' if len(rows) != 1 else ''}", badges)

    theme.detail_card("Vendor details", [
        theme.Field("Vendor", name),
        theme.Field("Material groups", _joined(rows["golongan"])),
        theme.Field("Allocation", _joined(rows["nib_lokasi"])),
        theme.Field("NIB number", _joined(rows["nib_nomor"])),
        theme.Field("NIB date", _joined(rows["nib_tanggal"].map(_fmt_date))),
        theme.Field("Smart Comp", _joined(rows["smart_comp"])),
    ])
    theme.people_card(f"Contacts / PIC ({len(_people(rows))})", _people(rows), "No PIC recorded for this vendor yet.")

    holder_names = {k: next(_text(v) for v in rows["iup_nama"] if normalize_name(v) == k) for k in holder_keys}
    monthly_section.render(ctx, "vendor", key, name, holder_names)

    theme.detail_title(f"IUP holders managed by {name}")
    if not holder_keys:
        st.caption("No IUP holder recorded for this vendor yet.")
    for i, holder_key in enumerate(holder_keys):
        _holder_summary(rows, holder_key, i)
    without = int((rows["iup_nama"].map(normalize_name) == "").sum())
    if without:
        st.caption(f"{without} record{'s' if without != 1 else ''} of this vendor have no IUP holder name yet.")


def _joined(values) -> str:
    return ", ".join(dict.fromkeys(_text(v) for v in values if _text(v)))


def _holder_summary(vendor_rows: pd.DataFrame, holder_key: str, i: int) -> None:
    rows = vendor_rows[vendor_rows["iup_nama"].map(normalize_name) == holder_key]
    first = rows.iloc[0]
    status = row_status(rows.iloc[[0]]).iloc[0]
    maps = _maps_link(rows)
    with st.container(border=True):
        theme.detail_header("", _text(first["iup_nama"]), "", [_status_badge(status)] + (
            [theme.badge(_fmt_days(first["iup_countdown"]), theme.CYAN)] if _fmt_days(first["iup_countdown"]) else []))
        theme.detail_card("Permit & location", [
            theme.Field("IUP number", _text(first["iup_nomor"])),
            theme.Field("Expiry date", _fmt_date(first["iup_tanggal_berakhir"])),
            theme.Field("Material group", _joined(rows["golongan"])),
            theme.Field("PIC", _joined(rows["nama_pic"])),
            theme.Field("Contact", html=" · ".join(
                filter(None, (_contact_html(c) for c in dict.fromkeys(rows["no_kontak"]))))),
            theme.Field("Google Maps", html=theme.link(maps, "Open in Google Maps ↗") if maps else ""),
        ])
        with st.container(horizontal=True, gap="small"):
            st.button("View holder details", icon=":material/badge:", key=f"to_holder_{holder_key}_{i}",
                      type="primary", on_click=_go, args=(KIND_HOLDER, holder_key, rows.index[0]))
            if maps:
                st.link_button("Open map", maps, icon=":material/map:")
