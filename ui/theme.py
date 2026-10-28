"""Design system: global CSS plus small HTML building blocks (page header, KPI cards, steps, legend, brand)."""
import html
from dataclasses import dataclass
from typing import Iterable, Sequence, Tuple

import streamlit as st

# Accent colors (also used by the KPI cards and legend chips).
INDIGO = "#818CF8"
CYAN = "#22D3EE"
GREEN = "#34D399"
RED = "#F87171"
AMBER = "#FBBF24"
SLATE = "#94A3B8"

_CSS = """
:root{
  --q-bg:#080B14; --q-surface:rgba(18,25,43,.72); --q-surface-solid:#121A2C;
  --q-border:rgba(148,163,184,.14); --q-border-strong:rgba(148,163,184,.24);
  --q-text:#E6E9F2; --q-muted:#94A3B8; --q-indigo:#818CF8; --q-cyan:#22D3EE;
  --q-grad:linear-gradient(135deg,#4F46E5 0%,#0891B2 100%);
}
/* ---------- canvas ---------- */
.stApp{
  background:
    radial-gradient(1100px 520px at -5% -12%, rgba(99,102,241,.16), transparent 62%),
    radial-gradient(900px 480px at 105% -8%, rgba(34,211,238,.09), transparent 60%),
    var(--q-bg);
}
[data-testid="stHeader"]{background:transparent;}
[data-testid="stMainBlockContainer"]{padding-top:2.4rem; padding-bottom:4rem; max-width:1480px;}
footer{visibility:hidden;}

/* ---------- sidebar ---------- */
[data-testid="stSidebar"]{border-right:1px solid var(--q-border);}
[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"]{border-radius:10px; padding:.45rem .7rem; transition:background .15s ease;}
[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"]:hover{background:rgba(129,140,248,.10);}

/* ---------- buttons ---------- */
button[data-testid^="stBaseButton-primary"]{
  background:var(--q-grad)!important; border:0!important; color:#fff!important;
  box-shadow:0 6px 18px rgba(79,70,229,.28); transition:transform .15s ease, box-shadow .15s ease, filter .15s ease;
}
button[data-testid^="stBaseButton-primary"]:hover{transform:translateY(-1px); box-shadow:0 10px 26px rgba(79,70,229,.40); filter:brightness(1.07);}
button[data-testid^="stBaseButton-primary"]:disabled{opacity:.4; box-shadow:none; transform:none; filter:none;}
button[data-testid^="stBaseButton-secondary"]{transition:border-color .15s ease, background .15s ease;}
button[data-testid^="stBaseButton-secondary"]:hover{border-color:var(--q-indigo)!important; background:rgba(129,140,248,.08)!important;}

/* ---------- containers ---------- */
[data-testid="stExpander"] details{border-radius:14px; border-color:var(--q-border); background:var(--q-surface);}
[data-testid="stForm"]{border-radius:18px; border-color:var(--q-border-strong); background:var(--q-surface); padding:1.4rem 1.4rem 1rem;
  box-shadow:0 20px 60px rgba(0,0,0,.35);}
[data-testid="stDataFrame"]{border-radius:12px; overflow:hidden;}
[data-testid="stFileUploaderDropzone"]{border-radius:14px; border:1px dashed rgba(129,140,248,.45); background:rgba(99,102,241,.05);}
[data-testid="stAlert"]{border-radius:12px;}
[data-testid="stPopoverBody"]{border-radius:14px; border:1px solid var(--q-border-strong);}

/* ---------- tabs ---------- */
.stTabs [data-baseweb="tab-list"]{gap:4px; border-bottom:1px solid var(--q-border);}
.stTabs [data-baseweb="tab"]{padding:10px 16px; border-radius:10px 10px 0 0; font-weight:500;}
.stTabs [data-baseweb="tab"][aria-selected="true"]{background:rgba(129,140,248,.10);}
.stTabs [data-baseweb="tab-highlight"]{background:linear-gradient(90deg,#6366F1,#22D3EE); height:2px;}

/* ---------- page header ---------- */
.q-eyebrow{font-size:.72rem; letter-spacing:.16em; text-transform:uppercase; color:var(--q-cyan); font-weight:600;}
.q-title{font-size:2.05rem; font-weight:750; letter-spacing:-.02em; line-height:1.15; margin:.2rem 0 .35rem;
  background:linear-gradient(90deg,#F8FAFC 0%,#C7D2FE 55%,#67E8F9 100%); -webkit-background-clip:text; background-clip:text; color:transparent;}
.q-sub{color:var(--q-muted); font-size:.98rem; max-width:780px; line-height:1.5;}
.q-header{margin-bottom:.4rem;}

/* ---------- section title ---------- */
.q-section{margin:1.4rem 0 .1rem; display:flex; align-items:flex-end; justify-content:space-between; gap:12px;}
.q-section-title{font-size:1.15rem; font-weight:650; color:#F1F5F9; letter-spacing:-.01em;}
.q-section-desc{font-size:.85rem; color:var(--q-muted); margin-top:2px;}

/* ---------- KPI cards ---------- */
.q-kpis{display:grid; grid-template-columns:repeat(auto-fit,minmax(190px,1fr)); gap:14px; margin:.6rem 0 .4rem;}
.q-kpi{position:relative; padding:16px 18px 14px; border-radius:16px; overflow:hidden;
  background:linear-gradient(180deg,rgba(22,30,52,.88),rgba(13,18,32,.88)); border:1px solid var(--q-border);}
.q-kpi::before{content:""; position:absolute; left:0; right:0; top:0; height:2px; background:var(--accent); opacity:.9;}
.q-kpi::after{content:""; position:absolute; right:-40px; top:-40px; width:120px; height:120px; border-radius:50%;
  background:radial-gradient(circle, var(--accent) 0%, transparent 70%); opacity:.10;}
.q-kpi-label{font-size:.8rem; color:var(--q-muted); display:flex; align-items:center; gap:8px; font-weight:500;}
.q-dot{width:8px; height:8px; border-radius:50%; background:var(--accent); box-shadow:0 0 10px var(--accent);}
.q-kpi-value{font-size:1.95rem; font-weight:700; margin-top:6px; font-variant-numeric:tabular-nums; color:#F8FAFC; letter-spacing:-.02em;}
.q-kpi-caption{font-size:.76rem; color:var(--q-muted); margin-top:2px;}

/* ---------- steps ---------- */
.q-steps{display:flex; flex-wrap:wrap; gap:8px; margin:.35rem 0 .9rem; align-items:center;}
.q-step{display:flex; align-items:center; gap:9px; padding:6px 14px 6px 6px; border-radius:999px;
  border:1px solid var(--q-border); background:rgba(20,27,46,.6); font-size:.84rem; color:#CBD5E1;}
.q-step-n{width:24px; height:24px; border-radius:50%; display:grid; place-items:center; font-weight:700; font-size:.74rem;
  background:var(--q-grad); color:#fff;}
.q-step-arrow{color:#475569; font-size:.9rem;}

/* ---------- legend & chips ---------- */
.q-legend{display:flex; flex-wrap:wrap; gap:8px; margin:.2rem 0 .5rem;}
.q-chip{display:inline-flex; align-items:center; gap:7px; padding:4px 11px; border-radius:999px; font-size:.78rem;
  border:1px solid var(--q-border); background:rgba(255,255,255,.02); color:#CBD5E1;}
.q-swatch{width:10px; height:10px; border-radius:3px; background:var(--accent);}

/* ---------- empty state ---------- */
.q-empty{border:1px dashed rgba(148,163,184,.28); border-radius:16px; padding:30px 24px; text-align:center;
  color:var(--q-muted); background:rgba(20,27,46,.35); margin:.4rem 0;}
.q-empty-icon{font-size:1.9rem; line-height:1;}
.q-empty-title{color:#E2E8F0; font-weight:600; font-size:1.02rem; margin:.55rem 0 .25rem;}
.q-empty-text{font-size:.88rem; max-width:560px; margin:0 auto; line-height:1.5;}

/* ---------- brand & user ---------- */
.q-brand{display:flex; align-items:center; gap:12px; padding:2px 2px 10px;}
.q-logo{width:40px; height:40px; border-radius:12px; display:grid; place-items:center; font-weight:800; color:#fff;
  background:linear-gradient(135deg,#6366F1 0%,#22D3EE 100%); box-shadow:0 8px 24px rgba(99,102,241,.35); flex:none;}
.q-brand-name{font-weight:700; font-size:1.02rem; color:#F8FAFC; line-height:1.15; letter-spacing:-.01em;}
.q-brand-tag{font-size:.73rem; color:var(--q-muted);}
.q-nav-label{font-size:.68rem; letter-spacing:.14em; text-transform:uppercase; color:#64748B; font-weight:600; margin:.6rem 0 .1rem .2rem;}
.q-user{display:flex; align-items:center; gap:10px; padding:10px 12px; border:1px solid var(--q-border); border-radius:12px;
  background:rgba(20,27,46,.6); margin-bottom:.5rem;}
.q-avatar{width:34px; height:34px; border-radius:50%; display:grid; place-items:center; font-weight:700; font-size:.85rem;
  background:rgba(99,102,241,.22); color:#C7D2FE; flex:none;}
.q-user-name{font-weight:600; color:#E2E8F0; font-size:.9rem; line-height:1.2;}
.q-user-role{font-size:.72rem; color:var(--q-muted);}
.q-guide{font-size:.82rem; color:#CBD5E1; line-height:1.55;}
.q-guide ol{padding-left:1.1rem; margin:.2rem 0;}
.q-guide li{margin-bottom:.35rem;}

/* ---------- login ---------- */
.q-login-hero{text-align:center; margin:9vh 0 20px;}
.q-login-hero .q-logo{width:58px; height:58px; margin:0 auto 16px; font-size:1.45rem; border-radius:17px;}
.q-login-title{font-size:1.65rem; font-weight:750; color:#F8FAFC; letter-spacing:-.02em;}
.q-login-sub{color:var(--q-muted); font-size:.92rem; margin-top:4px;}
.q-login-foot{text-align:center; color:#64748B; font-size:.78rem; margin-top:14px; line-height:1.5;}

@media (max-width: 640px){
  [data-testid="stMainBlockContainer"]{padding-top:1.4rem;}
  .q-title{font-size:1.6rem;}
  .q-kpi-value{font-size:1.55rem;}
}
"""


def inject() -> None:
    """Add the global stylesheet (call once per run, right after `st.set_page_config`)."""
    st.html(f"<style>{_CSS}</style>")


def _e(text) -> str:
    return html.escape(str(text))


def _render(markup: str) -> None:
    st.html(markup)


# ------------------------------------------------------------------ page structure
def page_header(eyebrow: str, title: str, subtitle: str) -> None:
    _render(
        f'<div class="q-header"><div class="q-eyebrow">{_e(eyebrow)}</div>'
        f'<div class="q-title">{_e(title)}</div><div class="q-sub">{_e(subtitle)}</div></div>'
    )


def section(title: str, description: str = "") -> None:
    desc = f'<div class="q-section-desc">{_e(description)}</div>' if description else ""
    _render(f'<div class="q-section"><div><div class="q-section-title">{_e(title)}</div>{desc}</div></div>')


@dataclass(frozen=True)
class Kpi:
    label: str
    value: str
    caption: str = ""
    accent: str = INDIGO


def kpi_cards(items: Sequence[Kpi]) -> None:
    cards = "".join(
        f'<div class="q-kpi" style="--accent:{item.accent}">'
        f'<div class="q-kpi-label"><span class="q-dot"></span>{_e(item.label)}</div>'
        f'<div class="q-kpi-value">{_e(item.value)}</div>'
        f'<div class="q-kpi-caption">{_e(item.caption)}</div></div>'
        for item in items
    )
    _render(f'<div class="q-kpis">{cards}</div>')


def steps(labels: Iterable[str]) -> None:
    """Numbered guide, e.g. 1 Upload -> 2 Review -> 3 Save."""
    parts = []
    for number, label in enumerate(labels, start=1):
        if number > 1:
            parts.append('<span class="q-step-arrow">→</span>')
        parts.append(f'<span class="q-step"><span class="q-step-n">{number}</span>{_e(label)}</span>')
    _render(f'<div class="q-steps">{"".join(parts)}</div>')


def legend(items: Iterable[Tuple[str, str]]) -> None:
    """Color legend: (label, color) pairs."""
    chips = "".join(
        f'<span class="q-chip"><span class="q-swatch" style="--accent:{color}"></span>{_e(label)}</span>'
        for label, color in items
    )
    _render(f'<div class="q-legend">{chips}</div>')


def empty_state(icon: str, title: str, text: str) -> None:
    _render(
        f'<div class="q-empty"><div class="q-empty-icon">{_e(icon)}</div>'
        f'<div class="q-empty-title">{_e(title)}</div><div class="q-empty-text">{_e(text)}</div></div>'
    )


# ------------------------------------------------------------------ brand, user, guide
APP_NAME = "QUICK Andesit"
APP_TAGLINE = "Quarry Information Checklist"


def brand() -> None:
    _render(
        f'<div class="q-brand"><div class="q-logo">Q</div><div>'
        f'<div class="q-brand-name">{_e(APP_NAME)}</div><div class="q-brand-tag">{_e(APP_TAGLINE)}</div>'
        f'</div></div>'
    )


def nav_label(text: str) -> None:
    _render(f'<div class="q-nav-label">{_e(text)}</div>')


def user_card(username: str) -> None:
    initials = (username[:2] or "?").upper()
    _render(
        f'<div class="q-user"><div class="q-avatar">{_e(initials)}</div><div>'
        f'<div class="q-user-name">{_e(username)}</div><div class="q-user-role">Signed in</div></div></div>'
    )


def guide(items: Iterable[str]) -> None:
    """Ordered list of short tips (plain text, escaped)."""
    rows = "".join(f"<li>{_e(item)}</li>" for item in items)
    _render(f'<div class="q-guide"><ol>{rows}</ol></div>')


def login_hero() -> None:
    _render(
        f'<div class="q-login-hero"><div class="q-logo">Q</div>'
        f'<div class="q-login-title">Welcome back</div>'
        f'<div class="q-login-sub">Sign in to {_e(APP_NAME)} · {_e(APP_TAGLINE)}</div></div>'
    )


def login_footer() -> None:
    _render(
        '<div class="q-login-foot">Access is limited to authorised procurement staff.<br>'
        'Need an account? Ask your administrator.</div>'
    )


def fmt_int(value) -> str:
    """12345 -> '12,345'."""
    return f"{int(value):,}"
