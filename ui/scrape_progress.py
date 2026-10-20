"""Tampilan progres scraping: kartu kecil minimalis (HTML + CSS) yang diperbarui langsung di layar."""
import html
import time
from typing import Optional

from minerba_scraper import STAGE_COMPANIES, STAGE_DONE, STAGE_PERMITS, STAGE_SAVE, ScrapeProgress

_STEPS = [(STAGE_COMPANIES, "Perusahaan"), (STAGE_PERMITS, "Izin"), (STAGE_SAVE, "Simpan")]
_STAGE_INDEX = {STAGE_COMPANIES: 0, STAGE_PERMITS: 1, STAGE_SAVE: 2, STAGE_DONE: 3}
_STAGE_TITLE = {
    STAGE_COMPANIES: "Mengambil daftar perusahaan",
    STAGE_PERMITS: "Mengekstrak izin",
    STAGE_SAVE: "Menyimpan ke database",
    STAGE_DONE: "Selesai",
}
# Bobot bar keseluruhan (persen): tahap perusahaan singkat, izin paling lama.
_WEIGHTS = {STAGE_COMPANIES: (0, 5), STAGE_PERMITS: (5, 90), STAGE_SAVE: (90, 100)}

_CSS = """<style>
.sp{max-width:440px;padding:10px 14px;border:1px solid rgba(128,128,128,.28);border-radius:12px;font-size:.8rem;line-height:1.35;margin:6px auto}
.sp-overlay{position:fixed;inset:0;z-index:999999;display:flex;align-items:center;justify-content:center;background:rgba(128,128,128,.28);-webkit-backdrop-filter:blur(4px);backdrop-filter:blur(4px)}
.sp-overlay .sp{width:min(380px,88vw);padding:16px 18px;margin:0;background:rgba(128,128,128,.24);-webkit-backdrop-filter:blur(14px);backdrop-filter:blur(14px);box-shadow:0 8px 32px rgba(0,0,0,.22)}
.sp-top{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:7px}
.sp-title{font-weight:600}
.sp-pct{opacity:.65;font-variant-numeric:tabular-nums}
.sp-track{height:4px;border-radius:99px;background:rgba(128,128,128,.22);overflow:hidden}
.sp-fill{height:100%;border-radius:99px;background:linear-gradient(90deg,#6366f1,#22d3ee);transition:width .25s ease}
.sp-fill.busy{width:30%;animation:sp-slide 1.1s ease-in-out infinite}
.sp-fill.ok{background:linear-gradient(90deg,#22c55e,#4ade80)}
.sp-fill.err{background:#ef4444}
@keyframes sp-slide{0%{margin-left:-30%}100%{margin-left:100%}}
.sp-meta{margin-top:7px;opacity:.75;font-variant-numeric:tabular-nums}
.sp-steps{display:flex;gap:12px;margin-top:8px;font-size:.7rem;opacity:.85}
.sp-dot{display:inline-block;width:6px;height:6px;border-radius:50%;background:rgba(128,128,128,.45);margin-right:5px}
.sp-step.on .sp-dot{background:#6366f1;box-shadow:0 0 0 3px rgba(99,102,241,.2)}
.sp-step.done .sp-dot{background:#22c55e}
.sp-warn{color:#f59e0b}
</style>"""


def _num(value: int) -> str:
    """12345 -> '12.345' (pemisah ribuan gaya Indonesia)."""
    return f"{int(value):,}".replace(",", ".")


def _clock(seconds: float) -> str:
    seconds = int(seconds)
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


def percent(p: ScrapeProgress) -> int:
    """Persen keseluruhan (0-100) dari tahap dan jumlah yang selesai."""
    if p.stage == STAGE_DONE:
        return 100
    start, end = _WEIGHTS[p.stage]
    fraction = min(1.0, p.done / p.total) if p.total else 0.0
    return int(round(start + (end - start) * fraction))


def _meta(p: ScrapeProgress) -> str:
    if p.stage == STAGE_COMPANIES:
        return html.escape(p.message or _STAGE_TITLE[STAGE_COMPANIES])
    if p.stage == STAGE_PERMITS:
        parts = [f"{_num(p.done)}/{_num(p.total)} perusahaan", f"{_num(p.permits)} izin"]
        if p.rate:
            parts.append(f"{p.rate:.0f}/dtk")
        parts.append(_clock(p.elapsed))
    elif p.stage == STAGE_SAVE:
        parts = [f"{_num(p.done)}/{_num(p.total)} paket", f"{_num(p.permits)} izin", _clock(p.elapsed)]
    else:
        parts = [f"{_num(p.total)} perusahaan", f"{_num(p.permits)} izin", _clock(p.elapsed)]
    text = " · ".join(parts)
    if p.failed:
        text += f' · <span class="sp-warn">⚠ {_num(p.failed)} gagal</span>'
    return text


def _steps(p: ScrapeProgress) -> str:
    current = _STAGE_INDEX[p.stage]
    items = []
    for key, label in _STEPS:
        index = _STAGE_INDEX[key]
        state = "done" if index < current else "on" if index == current else ""
        items.append(f'<span class="sp-step {state}"><span class="sp-dot"></span>{label}</span>')
    return "".join(items)


def render_progress_html(p: ScrapeProgress, caption: Optional[str] = None, overlay: bool = False) -> str:
    """
    Kartu progres sebagai satu baris HTML (tanpa baris kosong/indentasi agar tidak dibaca sebagai kode).
    overlay=True: kartu melayang tepat di tengah layar (dipakai saat scraping berjalan).
    """
    finished = p.stage == STAGE_DONE
    busy = p.stage == STAGE_COMPANIES and not p.total
    fill_class = "sp-fill ok" if finished else "sp-fill busy" if busy else "sp-fill"
    width = "" if busy else f' style="width:{percent(p)}%"'
    title = p.message if (p.stage == STAGE_PERMITS or finished) and p.message else _STAGE_TITLE[p.stage]
    title = ("✓ " if finished else "") + title
    extra = f" · {html.escape(caption)}" if caption else ""
    card = (
        f'<div class="sp">'
        f'<div class="sp-top"><span class="sp-title">{html.escape(title)}</span>'
        f'<span class="sp-pct">{percent(p)}%</span></div>'
        f'<div class="sp-track"><div class="{fill_class}"{width}></div></div>'
        f'<div class="sp-meta">{_meta(p)}{extra}</div>'
        f'<div class="sp-steps">{_steps(p)}</div></div>'
    )
    return f'{_CSS}<div class="sp-overlay">{card}</div>' if overlay else f"{_CSS}{card}"


def render_error_html(message: str) -> str:
    return (
        f'{_CSS}<div class="sp"><div class="sp-top"><span class="sp-title">Scraping gagal</span></div>'
        f'<div class="sp-track"><div class="sp-fill err" style="width:100%"></div></div>'
        f'<div class="sp-meta">{html.escape(message)}</div></div>'
    )


class ScrapeProgressView:
    """Menggambar progres ke satu placeholder Streamlit (`st.empty()`), dibatasi agar UI tidak tersendat."""

    def __init__(self, slot, min_interval: float = 0.15):
        self._slot = slot
        self._min_interval = min_interval
        self._last_draw = 0.0
        self._last_stage: Optional[str] = None
        self.last: Optional[ScrapeProgress] = None

    def update(self, p: ScrapeProgress) -> None:
        """Dipakai sebagai callback `on_progress` pada scraper."""
        self.last = p
        now = time.monotonic()
        important = p.stage != self._last_stage or p.stage == STAGE_DONE or (p.total and p.done >= p.total)
        if important or now - self._last_draw >= self._min_interval:
            self._slot.markdown(render_progress_html(p, overlay=True), unsafe_allow_html=True)
            self._last_draw, self._last_stage = now, p.stage

    def fail(self, message: str) -> None:
        self._slot.markdown(render_error_html(message), unsafe_allow_html=True)


def show_summary(slot, p: ScrapeProgress, caption: Optional[str] = None) -> None:
    """Tampilkan ringkasan pembaruan terakhir (kartu selesai) pada placeholder."""
    slot.markdown(render_progress_html(p, caption), unsafe_allow_html=True)
