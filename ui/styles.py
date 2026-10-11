"""Tampilan tabel: konfigurasi kolom dan pewarnaan baris."""
import pandas as pd
import streamlit as st

from core.schema import AUTO_COLS, AUTO_TAG, DB_COLS, pretty_label

ROW_RED = "background-color: rgba(239, 68, 68, 0.16)"
ROW_YELLOW = "background-color: rgba(250, 204, 21, 0.20)"

_COLUMN_WIDTHS = {
    "vendor": "large", "nama_pic": "medium", "no_kontak": "medium",
    "nib_lokasi": "large", "surat_dukungan_lokasi_quarry": "large",
    "iup_nama": "large", "remark": "large",
    "minerbaone": "small", "smart_comp": "small", "iup_countdown": "small", "iup_periode": "small",
}


def build_vendor_column_config() -> dict:
    """Label rapi, lebar sesuai isi, kolom otomatis dikunci, IUP NAMA di-freeze."""
    config = {}
    for column in DB_COLS:
        options = dict(label=pretty_label(column), width=_COLUMN_WIDTHS.get(column, "medium"))
        if column in AUTO_COLS:
            options["disabled"] = True
            options["help"] = "Terisi otomatis dari data Minerba / perhitungan tanggal."
        if column == "iup_nama":
            try:
                config[column] = st.column_config.TextColumn(pinned=True, **options)
                continue
            except TypeError:  # Streamlit versi lama tidak punya 'pinned'
                pass
        config[column] = st.column_config.TextColumn(**options)
    return config


def style_rows(df: pd.DataFrame):
    """Merah: IUP NAMA terisi tapi tidak ada di ESDM. Kuning: IUP akan/sudah berakhir (ada peringatan)."""
    def color(row):
        iup_name = str(row.get("iup_nama", "")).strip()
        if iup_name and row.get("minerbaone") != "Valid":
            css = ROW_RED
        elif AUTO_TAG in str(row.get("remark", "")):
            css = ROW_YELLOW
        else:
            css = ""
        return [css] * len(row)

    return df.style.apply(color, axis=1)


def pretty_minerba_config(df: pd.DataFrame) -> dict:
    return {
        column: st.column_config.TextColumn(label=column.replace("_", " ").title(), width="medium")
        for column in df.columns
    }
