"""Scraping progress display: a small, minimal card (HTML + CSS) updated live on screen.
Colors come from the light/dark variables defined in ui/theme.py."""
import html
import time
from typing import Optional

from minerba_scraper import STAGE_COMPANIES, STAGE_DONE, STAGE_PERMITS, STAGE_SAVE, ScrapeProgress

_STEPS = [(STAGE_COMPANIES, "Companies"), (STAGE_PERMITS, "Permits"), (STAGE_SAVE, "Save")]
_STAGE_INDEX = {STAGE_COMPANIES: 0, STAGE_PERMITS: 1, STAGE_SAVE: 2, STAGE_DONE: 3}
_STAGE_TITLE = {
    STAGE_COMPANIES: "Fetching company list",
    STAGE_PERMITS: "Extracting permits",
    STAGE_SAVE: "Saving to database",
    STAGE_DONE: "Done",
}
# Weight of each stage in the overall bar (percent): the company stage is short, permits take longest.
_WEIGHTS = {STAGE_COMPANIES: (0, 5), STAGE_PERMITS: (5, 90), STAGE_SAVE: (90, 100)}

_CSS = """<style>
.sp{max-width:460px;padding:14px 16px;border:1px solid var(--q-border-strong);border-radius:14px;font-size:.82rem;line-height:1.4;margin:6px 0;background:var(--q-kpi-bg);box-shadow:var(--q-card-shadow)}
.sp-overlay{position:fixed;inset:0;z-index:999999;display:flex;align-items:center;justify-content:center;background:var(--q-overlay);-webkit-backdrop-filter:blur(6px);backdrop-filter:blur(6px)}
.sp-overlay .sp{width:min(420px,90vw);padding:20px 22px;margin:0;box-shadow:var(--q-shadow-lg)}
.sp-top{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:9px;gap:10px}
.sp-title{font-weight:600;color:var(--q-heading)}
.sp-pct{color:var(--q-pct);font-weight:600;font-variant-numeric:tabular-nums}
.sp-track{height:6px;border-radius:99px;background:var(--q-track);overflow:hidden}
.sp-fill{height:100%;border-radius:99px;background:linear-gradient(90deg,#6366F1,#22D3EE);box-shadow:0 0 12px rgba(34,211,238,.45);transition:width .25s ease}
.sp-fill.busy{width:30%;animation:sp-slide 1.1s ease-in-out infinite}
.sp-fill.ok{background:linear-gradient(90deg,#10B981,#34D399);box-shadow:none}
.sp-fill.err{background:#F87171;box-shadow:none}
@keyframes sp-slide{0%{margin-left:-30%}100%{margin-left:100%}}
.sp-meta{margin-top:9px;color:var(--q-muted);font-variant-numeric:tabular-nums}
.sp-steps{display:flex;gap:14px;margin-top:10px;font-size:.74rem;color:var(--q-text-soft)}
.sp-dot{display:inline-block;width:7px;height:7px;border-radius:50%;background:rgba(148,163,184,.45);margin-right:6px}
.sp-step.on .sp-dot{background:#818CF8;box-shadow:0 0 0 3px rgba(129,140,248,.25)}
.sp-step.done .sp-dot{background:#34D399}
.sp-warn{color:color-mix(in srgb,#FBBF24 var(--q-accent-ink),var(--q-heading))}
.sp-hint{margin-top:10px;font-size:.74rem;color:var(--q-faint)}
</style>"""


def _num(value: int) -> str:
    """12345 -> '12,345'."""
    return f"{int(value):,}"


def _clock(seconds: float) -> str:
    seconds = int(seconds)
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


def percent(p: ScrapeProgress) -> int:
    """Overall percent (0-100) from the stage and the amount done."""
    if p.stage == STAGE_DONE:
        return 100
    start, end = _WEIGHTS[p.stage]
    fraction = min(1.0, p.done / p.total) if p.total else 0.0
    return int(round(start + (end - start) * fraction))


def _meta(p: ScrapeProgress) -> str:
    if p.stage == STAGE_COMPANIES:
        return html.escape(p.message or _STAGE_TITLE[STAGE_COMPANIES])
    if p.stage == STAGE_PERMITS:
        parts = [f"{_num(p.done)}/{_num(p.total)} companies", f"{_num(p.permits)} permits"]
        if p.rate:
            parts.append(f"{p.rate:.0f}/s")
        parts.append(_clock(p.elapsed))
    elif p.stage == STAGE_SAVE:
        parts = [f"{_num(p.done)}/{_num(p.total)} batches", f"{_num(p.permits)} permits", _clock(p.elapsed)]
    else:
        parts = [f"{_num(p.total)} companies", f"{_num(p.permits)} permits", _clock(p.elapsed)]
    text = " · ".join(parts)
    if p.failed:
        text += f' · <span class="sp-warn">⚠ {_num(p.failed)} failed</span>'
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
    The progress card as one line of HTML (no blank lines/indentation, so markdown never reads it as code).
    overlay=True: the card floats in the middle of the screen (used while scraping runs).
    """
    finished = p.stage == STAGE_DONE
    busy = p.stage == STAGE_COMPANIES and not p.total
    fill_class = "sp-fill ok" if finished else "sp-fill busy" if busy else "sp-fill"
    width = "" if busy else f' style="width:{percent(p)}%"'
    title = p.message if (p.stage == STAGE_PERMITS or finished) and p.message else _STAGE_TITLE[p.stage]
    title = ("✓ " if finished else "") + title
    extra = f" · {html.escape(caption)}" if caption else ""
    hint = '<div class="sp-hint">Please keep this page open until it finishes.</div>' if overlay else ""
    card = (
        f'<div class="sp">'
        f'<div class="sp-top"><span class="sp-title">{html.escape(title)}</span>'
        f'<span class="sp-pct">{percent(p)}%</span></div>'
        f'<div class="sp-track"><div class="{fill_class}"{width}></div></div>'
        f'<div class="sp-meta">{_meta(p)}{extra}</div>'
        f'<div class="sp-steps">{_steps(p)}</div>{hint}</div>'
    )
    return f'{_CSS}<div class="sp-overlay">{card}</div>' if overlay else f"{_CSS}{card}"


def render_error_html(message: str) -> str:
    return (
        f'{_CSS}<div class="sp"><div class="sp-top"><span class="sp-title">Refresh failed · '
        f'your existing data was kept</span></div>'
        f'<div class="sp-track"><div class="sp-fill err" style="width:100%"></div></div>'
        f'<div class="sp-meta">{html.escape(message)}</div></div>'
    )


class ScrapeProgressView:
    """Draws progress into one Streamlit placeholder (`st.empty()`), throttled so the UI stays smooth."""

    def __init__(self, slot, min_interval: float = 0.15):
        self._slot = slot
        self._min_interval = min_interval
        self._last_draw = 0.0
        self._last_stage: Optional[str] = None
        self.last: Optional[ScrapeProgress] = None

    def update(self, p: ScrapeProgress) -> None:
        """Used as the scraper's `on_progress` callback."""
        self.last = p
        now = time.monotonic()
        important = p.stage != self._last_stage or p.stage == STAGE_DONE or (p.total and p.done >= p.total)
        if important or now - self._last_draw >= self._min_interval:
            self._slot.markdown(render_progress_html(p, overlay=True), unsafe_allow_html=True)
            self._last_draw, self._last_stage = now, p.stage

    def fail(self, message: str) -> None:
        self._slot.markdown(render_error_html(message), unsafe_allow_html=True)


def show_summary(slot, p: ScrapeProgress, caption: Optional[str] = None) -> None:
    """Show the summary of the last refresh (the finished card) in the placeholder."""
    slot.markdown(render_progress_html(p, caption), unsafe_allow_html=True)
