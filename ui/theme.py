"""Design system: global CSS plus small HTML building blocks (page header, KPI cards, steps, legend, brand)."""
import html
from dataclasses import dataclass
from typing import Callable, Iterable, Optional, Sequence, Tuple

import streamlit as st

# Accent colors (also used by the KPI cards and legend chips).
INDIGO = "#818CF8"
CYAN = "#22D3EE"
GREEN = "#34D399"
RED = "#F87171"
AMBER = "#FBBF24"
SLATE = "#94A3B8"

# Color tokens per mode. Every color in the stylesheet below comes from one of these variables, so the
# two modes only differ here. Accent colors (KPI, badges) stay the same; text drawn in an accent color is
# mixed with dark ink in light mode (--q-accent-ink) so it stays readable on white.
_TOKENS = {
    "dark": """
  --q-bg:#080B14; --q-glow-1:rgba(99,102,241,.16); --q-glow-2:rgba(34,211,238,.09);
  --q-surface:rgba(18,25,43,.72); --q-card:rgba(20,27,46,.6); --q-card-soft:rgba(20,27,46,.35);
  --q-kpi-bg:linear-gradient(180deg,rgba(22,30,52,.88),rgba(13,18,32,.88));
  --q-kpi-active-bg:linear-gradient(180deg,rgba(30,40,70,.96),rgba(14,20,36,.94));
  --q-card-shadow:none; --q-shadow-lg:0 20px 60px rgba(0,0,0,.35);
  --q-border:rgba(148,163,184,.14); --q-border-strong:rgba(148,163,184,.24); --q-divider:rgba(148,163,184,.08);
  --q-dashed:rgba(148,163,184,.28);
  --q-heading:#F8FAFC; --q-text:#E2E8F0; --q-text-soft:#CBD5E1; --q-muted:#94A3B8; --q-faint:#64748B;
  --q-empty:#475569; --q-eyebrow:#22D3EE; --q-link:#67E8F9; --q-pct:#A5B4FC;
  --q-title-grad:linear-gradient(90deg,#F8FAFC 0%,#C7D2FE 55%,#67E8F9 100%);
  --q-hover:rgba(129,140,248,.10); --q-hover-strong:rgba(129,140,248,.08);
  --q-avatar-bg:rgba(99,102,241,.22); --q-avatar-fg:#C7D2FE;
  --q-wa-fg:#6EE7B7; --q-wa-bg:rgba(52,211,153,.1); --q-wa-border:rgba(52,211,153,.4);
  --q-drop-border:rgba(129,140,248,.45); --q-drop-bg:rgba(99,102,241,.05);
  --q-track:rgba(148,163,184,.14); --q-chip-bg:rgba(255,255,255,.02);
  --q-overlay:rgba(5,8,16,.55); --q-accent-ink:100%;
""",
    "light": """
  --q-bg:#F4F6FB; --q-glow-1:rgba(99,102,241,.10); --q-glow-2:rgba(34,211,238,.08);
  --q-surface:rgba(255,255,255,.92); --q-card:#FFFFFF; --q-card-soft:rgba(255,255,255,.7);
  --q-kpi-bg:linear-gradient(180deg,#FFFFFF,#F9FAFD);
  --q-kpi-active-bg:linear-gradient(180deg,#EEF0FF,#F8F9FF);
  --q-card-shadow:0 1px 2px rgba(15,23,42,.05), 0 4px 14px -6px rgba(15,23,42,.08);
  --q-shadow-lg:0 18px 50px rgba(15,23,42,.10);
  --q-border:rgba(15,23,42,.09); --q-border-strong:rgba(15,23,42,.15); --q-divider:rgba(15,23,42,.07);
  --q-dashed:rgba(15,23,42,.20);
  --q-heading:#0F172A; --q-text:#1E293B; --q-text-soft:#334155; --q-muted:#5B6678; --q-faint:#7A8597;
  --q-empty:#A3ADBD; --q-eyebrow:#0E7490; --q-link:#0E7490; --q-pct:#4338CA;
  --q-title-grad:linear-gradient(90deg,#0F172A 0%,#3730A3 55%,#0E7490 100%);
  --q-hover:rgba(99,102,241,.08); --q-hover-strong:rgba(99,102,241,.06);
  --q-avatar-bg:rgba(99,102,241,.12); --q-avatar-fg:#4338CA;
  --q-wa-fg:#047857; --q-wa-bg:rgba(16,185,129,.08); --q-wa-border:rgba(16,185,129,.35);
  --q-drop-border:rgba(99,102,241,.40); --q-drop-bg:rgba(99,102,241,.04);
  --q-track:rgba(15,23,42,.08); --q-chip-bg:#FFFFFF;
  --q-overlay:rgba(244,246,251,.65); --q-accent-ink:58%;
""",
}

_CSS = """
/* ---------- canvas ---------- */
.stApp{
  background:
    radial-gradient(1100px 520px at -5% -12%, var(--q-glow-1), transparent 62%),
    radial-gradient(900px 480px at 105% -8%, var(--q-glow-2), transparent 60%),
    var(--q-bg);
}
[data-testid="stHeader"]{background:transparent;}
[data-testid="stMainBlockContainer"]{padding-top:2.4rem; padding-bottom:4rem; max-width:1480px;}
footer{visibility:hidden;}
.st-key-q_theme_store{display:none!important;}

/* ---------- sidebar ---------- */
[data-testid="stSidebar"]{border-right:1px solid var(--q-border);}
[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"]{border-radius:10px; padding:.45rem .7rem; transition:background .15s ease;}
[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"]:hover{background:var(--q-hover);}

/* ---------- buttons ---------- */
button[data-testid^="stBaseButton-primary"]{
  background:var(--q-grad)!important; border:0!important; color:#fff!important;
  box-shadow:0 6px 18px rgba(79,70,229,.28); transition:transform .15s ease, box-shadow .15s ease, filter .15s ease;
}
button[data-testid^="stBaseButton-primary"]:hover{transform:translateY(-1px); box-shadow:0 10px 26px rgba(79,70,229,.40); filter:brightness(1.07);}
button[data-testid^="stBaseButton-primary"]:disabled{opacity:.4; box-shadow:none; transform:none; filter:none;}
button[data-testid^="stBaseButton-secondary"]{transition:border-color .15s ease, background .15s ease;}
button[data-testid^="stBaseButton-secondary"]:hover{border-color:var(--q-indigo)!important; background:var(--q-hover-strong)!important;}

/* ---------- containers ---------- */
[data-testid="stExpander"] details{border-radius:14px; border-color:var(--q-border); background:var(--q-surface);}
[data-testid="stForm"]{border-radius:18px; border-color:var(--q-border-strong); background:var(--q-surface); padding:1.4rem 1.4rem 1rem;
  box-shadow:var(--q-shadow-lg);}
/* no overflow:hidden here: it clips the table toolbar (delete rows, search, download) that sits above the grid */
[data-testid="stDataFrame"]{border-radius:12px;}
[data-testid="stFileUploaderDropzone"]{border-radius:14px; border:1px dashed var(--q-drop-border); background:var(--q-drop-bg);}
[data-testid="stAlert"]{border-radius:12px;}
[data-testid="stPopoverBody"]{border-radius:14px; border:1px solid var(--q-border-strong);}

/* ---------- tabs ---------- */
.stTabs [data-baseweb="tab-list"]{gap:4px; border-bottom:1px solid var(--q-border);}
.stTabs [data-baseweb="tab"]{padding:10px 16px; border-radius:10px 10px 0 0; font-weight:500;}
.stTabs [data-baseweb="tab"][aria-selected="true"]{background:var(--q-hover);}
.stTabs [data-baseweb="tab-highlight"]{background:linear-gradient(90deg,#6366F1,#22D3EE); height:2px;}

/* ---------- page header ---------- */
.q-eyebrow{font-size:.72rem; letter-spacing:.16em; text-transform:uppercase; color:var(--q-eyebrow); font-weight:600;}
.q-title{font-size:2.05rem; font-weight:750; letter-spacing:-.02em; line-height:1.15; margin:.2rem 0 .35rem;
  background:var(--q-title-grad); -webkit-background-clip:text; background-clip:text; color:transparent;}
.q-sub{color:var(--q-muted); font-size:.98rem; max-width:780px; line-height:1.5;}
.q-header{margin-bottom:.4rem;}

/* ---------- section title ---------- */
.q-section{margin:1.4rem 0 .1rem; display:flex; align-items:flex-end; justify-content:space-between; gap:12px;}
.q-section-title{font-size:1.15rem; font-weight:650; color:var(--q-heading); letter-spacing:-.01em;}
.q-section-desc{font-size:.85rem; color:var(--q-muted); margin-top:2px;}

/* ---------- KPI cards ---------- */
.q-kpis{display:grid; grid-template-columns:repeat(auto-fit,minmax(190px,1fr)); gap:14px; margin:.6rem 0 .4rem;}
.q-kpi{position:relative; padding:16px 18px 14px; border-radius:16px; overflow:hidden;
  background:var(--q-kpi-bg); border:1px solid var(--q-border); box-shadow:var(--q-card-shadow);}
.q-kpi::before{content:""; position:absolute; left:0; right:0; top:0; height:2px; background:var(--accent); opacity:.9;}
.q-kpi::after{content:""; position:absolute; right:-40px; top:-40px; width:120px; height:120px; border-radius:50%;
  background:radial-gradient(circle, var(--accent) 0%, transparent 70%); opacity:.10;}
.q-kpi-label{font-size:.8rem; color:var(--q-muted); display:flex; align-items:center; gap:8px; font-weight:500;}
.q-dot{width:8px; height:8px; border-radius:50%; background:var(--accent); box-shadow:0 0 10px var(--accent);}
.q-kpi-value{font-size:1.95rem; font-weight:700; margin-top:6px; font-variant-numeric:tabular-nums; color:var(--q-heading); letter-spacing:-.02em;}
.q-kpi-caption{font-size:.76rem; color:var(--q-muted); margin-top:2px;}

/* ---------- clickable KPI cards (same card, an invisible button on top) ---------- */
[class*="st-key-qkpicard_"]{position:relative; gap:0!important;}
[class*="st-key-qkpicard_"] .q-kpi{min-height:132px; cursor:pointer;
  transition:transform .16s ease, border-color .16s ease, box-shadow .16s ease;}
[class*="st-key-qkpicard_"]:hover .q-kpi{transform:translateY(-2px); border-color:var(--accent);
  box-shadow:0 14px 34px -18px var(--accent);}
[class*="st-key-qkpicard_"]:has(button:focus-visible) .q-kpi{outline:2px solid var(--accent); outline-offset:2px;}
[class*="st-key-qkpibtn_"]{position:absolute!important; inset:0; z-index:3; margin:0!important;}
[class*="st-key-qkpibtn_"] [data-testid="stButton"], [class*="st-key-qkpibtn_"] button{width:100%!important; height:100%!important;}
[class*="st-key-qkpibtn_"] button{opacity:0; cursor:pointer; min-height:0; padding:0;}
.q-kpi.is-active{border-color:var(--accent); background:var(--q-kpi-active-bg);
  box-shadow:0 0 0 1px var(--accent) inset, 0 16px 38px -16px var(--accent);}
.q-kpi.is-active::after{opacity:.2;}
.q-kpi-hint{font-size:.72rem; margin-top:10px; font-weight:600; opacity:.9;
  color:color-mix(in srgb, var(--accent) var(--q-accent-ink), var(--q-heading));}

/* ---------- detail dialog ---------- */
.q-dhead{padding:2px 0 12px; border-bottom:1px solid var(--q-border); margin-bottom:4px;}
.q-dhead-eyebrow{font-size:.7rem; letter-spacing:.14em; text-transform:uppercase; color:var(--q-eyebrow); font-weight:650;}
.q-dhead-title{font-size:1.4rem; font-weight:720; color:var(--q-heading); line-height:1.25; margin-top:2px; word-break:break-word;}
.q-dhead-sub{font-size:.86rem; color:var(--q-muted); margin-top:3px;}
.q-badges{display:flex; flex-wrap:wrap; gap:6px; margin-top:10px;}
.q-badge{display:inline-flex; align-items:center; gap:6px; padding:3px 10px; border-radius:999px; font-size:.76rem; font-weight:600;
  color:color-mix(in srgb, var(--accent) var(--q-accent-ink), var(--q-heading));
  background:color-mix(in srgb, var(--accent) 14%, transparent);
  border:1px solid color-mix(in srgb, var(--accent) 38%, transparent);}
.q-dcard{border:1px solid var(--q-border); border-radius:14px; background:var(--q-card); padding:12px 16px 8px; margin:10px 0 4px;
  box-shadow:var(--q-card-shadow);}
.q-dcard-title{font-size:.7rem; letter-spacing:.13em; text-transform:uppercase; color:var(--q-muted); font-weight:700; margin-bottom:4px;}
.q-field{display:grid; grid-template-columns:minmax(130px,36%) 1fr; gap:14px; padding:7px 0;
  border-top:1px solid var(--q-divider); font-size:.9rem; line-height:1.45;}
.q-dcard-title + .q-field{border-top:0;}
.q-field-label{color:var(--q-muted);}
.q-field-value{color:var(--q-text); word-break:break-word;}
.q-field-value.is-empty{color:var(--q-empty);}
.q-dialog a, .q-field-value a{color:var(--q-link); text-decoration:none; font-weight:550;}
.q-dialog a:hover, .q-field-value a:hover{text-decoration:underline;}
.q-person{display:flex; align-items:center; gap:12px; padding:9px 0; border-top:1px solid var(--q-divider);}
.q-dcard-title + .q-person{border-top:0;}
.q-person-main{flex:1; min-width:0;}
.q-person-name{color:var(--q-text); font-weight:600; font-size:.92rem;}
.q-person-sub{color:var(--q-muted); font-size:.8rem; margin-top:1px;}
.q-wa{flex:none; font-size:.8rem; padding:4px 10px; border-radius:999px; border:1px solid var(--q-wa-border);
  background:var(--q-wa-bg);}
.q-wa, .q-wa:hover{color:var(--q-wa-fg)!important;}
.q-progress{height:8px; border-radius:999px; background:var(--q-track); overflow:hidden; margin:8px 0 4px;}
.q-progress > span{display:block; height:100%; border-radius:999px; background:linear-gradient(90deg,#6366F1,#22D3EE);}
.q-progress-text{display:flex; justify-content:space-between; gap:10px; font-size:.8rem; color:var(--q-muted); flex-wrap:wrap;}
.q-note{font-size:.84rem; color:var(--q-text-soft); line-height:1.5;}
@media (max-width: 640px){ .q-field{grid-template-columns:1fr; gap:2px;} }

/* ---------- steps ---------- */
.q-steps{display:flex; flex-wrap:wrap; gap:8px; margin:.35rem 0 .9rem; align-items:center;}
.q-step{display:flex; align-items:center; gap:9px; padding:6px 14px 6px 6px; border-radius:999px;
  border:1px solid var(--q-border); background:var(--q-card); font-size:.84rem; color:var(--q-text-soft);}
.q-step-n{width:24px; height:24px; border-radius:50%; display:grid; place-items:center; font-weight:700; font-size:.74rem;
  background:var(--q-grad); color:#fff;}
.q-step-arrow{color:var(--q-faint); font-size:.9rem;}

/* ---------- legend & chips ---------- */
.q-legend{display:flex; flex-wrap:wrap; gap:8px; margin:.2rem 0 .5rem;}
.q-chip{display:inline-flex; align-items:center; gap:7px; padding:4px 11px; border-radius:999px; font-size:.78rem;
  border:1px solid var(--q-border); background:var(--q-chip-bg); color:var(--q-text-soft);}
.q-swatch{width:10px; height:10px; border-radius:3px; background:var(--accent);}

/* ---------- empty state ---------- */
.q-empty{border:1px dashed var(--q-dashed); border-radius:16px; padding:30px 24px; text-align:center;
  color:var(--q-muted); background:var(--q-card-soft); margin:.4rem 0;}
.q-empty-icon{font-size:1.9rem; line-height:1;}
.q-empty-title{color:var(--q-text); font-weight:600; font-size:1.02rem; margin:.55rem 0 .25rem;}
.q-empty-text{font-size:.88rem; max-width:560px; margin:0 auto; line-height:1.5;}

/* ---------- brand & user ---------- */
.q-brand{display:flex; align-items:center; gap:12px; padding:2px 2px 10px;}
.q-logo{width:40px; height:40px; border-radius:12px; display:grid; place-items:center; font-weight:800; color:#fff;
  background:linear-gradient(135deg,#6366F1 0%,#22D3EE 100%); box-shadow:0 8px 24px rgba(99,102,241,.35); flex:none;}
.q-brand-name{font-weight:700; font-size:1.02rem; color:var(--q-heading); line-height:1.15; letter-spacing:-.01em;}
.q-brand-tag{font-size:.73rem; color:var(--q-muted);}
.q-nav-label{font-size:.68rem; letter-spacing:.14em; text-transform:uppercase; color:var(--q-faint); font-weight:600; margin:.6rem 0 .1rem .2rem;}
.q-user{display:flex; align-items:center; gap:10px; padding:10px 12px; border:1px solid var(--q-border); border-radius:12px;
  background:var(--q-card); margin-bottom:.5rem;}
.q-avatar{width:34px; height:34px; border-radius:50%; display:grid; place-items:center; font-weight:700; font-size:.85rem;
  background:var(--q-avatar-bg); color:var(--q-avatar-fg); flex:none;}
.q-user-name{font-weight:600; color:var(--q-text); font-size:.9rem; line-height:1.2;}
.q-user-role{font-size:.72rem; color:var(--q-muted);}
.q-guide{font-size:.82rem; color:var(--q-text-soft); line-height:1.55;}
.q-guide ol{padding-left:1.1rem; margin:.2rem 0;}
.q-guide li{margin-bottom:.35rem;}

/* ---------- login ---------- */
.q-login-hero{text-align:center; margin:7vh 0 20px; animation:q-rise .45s ease both;}
.q-login-hero .q-logo{width:58px; height:58px; margin:0 auto 16px; font-size:1.45rem; border-radius:17px;}
.q-login-title{font-size:1.65rem; font-weight:750; color:var(--q-heading); letter-spacing:-.02em;}
.q-login-sub{color:var(--q-muted); font-size:.92rem; margin-top:4px;}
.q-login-foot{text-align:center; color:var(--q-faint); font-size:.78rem; margin-top:14px; line-height:1.5;}
.st-key-q_login [data-testid="stForm"]{animation:q-rise .45s .05s ease both;}
.st-key-q_login_theme{position:fixed; top:.75rem; right:1rem; z-index:999991; width:auto!important;}

/* ---------- loading screen (signing in, first load) ---------- */
.q-splash{position:fixed; inset:0; z-index:999995; display:flex; flex-direction:column; align-items:center; justify-content:center;
  gap:18px; background:
    radial-gradient(1100px 520px at -5% -12%, var(--q-glow-1), transparent 62%),
    radial-gradient(900px 480px at 105% -8%, var(--q-glow-2), transparent 60%),
    var(--q-bg);
  animation:q-fade .18s ease both;}
.q-splash .q-logo{width:58px; height:58px; font-size:1.45rem; border-radius:17px; animation:q-pulse 1.6s ease-in-out infinite;}
.q-splash-title{font-size:1.15rem; font-weight:650; color:var(--q-heading); letter-spacing:-.01em;}
.q-splash-sub{font-size:.86rem; color:var(--q-muted); margin-top:-10px;}
.q-splash-bar{width:180px; height:4px; border-radius:99px; background:var(--q-track); overflow:hidden;}
.q-splash-bar > span{display:block; width:40%; height:100%; border-radius:99px; background:linear-gradient(90deg,#6366F1,#22D3EE);
  animation:q-slide 1.1s ease-in-out infinite;}
/* the sign-in screen is shown by the browser the moment "Sign in" is pressed (class set in ui/login.py) */
.q-splash.is-login{display:none;}
body.q-signing-in .q-splash.is-login{display:flex;}
/* loading screens must not fade like the rest of the page while the app is busy */
[data-testid="stElementContainer"]:has(.q-splash){opacity:1!important; transition:none!important;}
@keyframes q-fade{from{opacity:0} to{opacity:1}}
@keyframes q-rise{from{opacity:0; transform:translateY(8px)} to{opacity:1; transform:none}}
@keyframes q-slide{0%{margin-left:-40%} 100%{margin-left:100%}}
@keyframes q-pulse{0%,100%{transform:scale(1)} 50%{transform:scale(1.06)}}

@media (max-width: 640px){
  [data-testid="stMainBlockContainer"]{padding-top:1.4rem;}
  .q-title{font-size:1.6rem;}
  .q-kpi-value{font-size:1.55rem;}
}
@media (prefers-reduced-motion: reduce){
  .q-login-hero, .st-key-q_login [data-testid="stForm"], .q-splash, .q-splash .q-logo, .q-splash-bar > span{animation:none!important;}
}
"""

_SHARED_TOKENS = "--q-indigo:#818CF8; --q-cyan:#22D3EE; --q-grad:linear-gradient(135deg,#4F46E5 0%,#0891B2 100%);"


def css_tokens(mode: str) -> str:
    """`:root` variables for one mode ('light' or 'dark')."""
    mode = mode if mode in _TOKENS else "dark"
    return f":root{{{_SHARED_TOKENS}{_TOKENS[mode]}color-scheme:{mode};}}"


def inject(mode: str = "dark") -> None:
    """Add the global stylesheet for the given mode (call once per run, right after `st.set_page_config`)."""
    st.html(f"<style>{css_tokens(mode)}{_CSS}</style>")


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


def _kpi_card(item: Kpi, active: bool = False, hint: str = "") -> str:
    hint_html = f'<div class="q-kpi-hint">{_e(hint)}</div>' if hint else ""
    return (
        f'<div class="q-kpi{" is-active" if active else ""}" style="--accent:{item.accent}">'
        f'<div class="q-kpi-label"><span class="q-dot"></span>{_e(item.label)}</div>'
        f'<div class="q-kpi-value">{_e(item.value)}</div>'
        f'<div class="q-kpi-caption">{_e(item.caption)}</div>{hint_html}</div>'
    )


def kpi_cards(items: Sequence[Kpi]) -> None:
    _render(f'<div class="q-kpis">{"".join(_kpi_card(item) for item in items)}</div>')


def clickable_kpi_cards(items: Sequence[Tuple[str, Kpi]], active: Optional[str], on_click: Callable[[str], None]) -> None:
    """
    The same KPI cards, but each card is a button: `on_click(key)` runs when a card is clicked.
    The active card is highlighted. (A transparent st.button is laid over the HTML card.)
    """
    columns = st.columns(len(items), gap="small")
    for column, (key, item) in zip(columns, items):
        is_active = key == active
        with column, st.container(key=f"qkpicard_{key}"):
            _render(_kpi_card(item, is_active, "Showing below · click to hide" if is_active else "Click to view list →"))
            st.button(f"{'Hide' if is_active else 'Show'} {item.label}", key=f"qkpibtn_{key}",
                      on_click=on_click, args=(key,))


# ------------------------------------------------------------------ detail dialog building blocks
def badge(text: str, color: str) -> str:
    return f'<span class="q-badge" style="--accent:{color}">{_e(text)}</span>'


def link(url: str, text: str, css_class: str = "") -> str:
    """External link (opens in a new tab). Only http(s) URLs are turned into links."""
    if not str(url).lower().startswith(("http://", "https://")):
        return _e(text)
    cls = f' class="{css_class}"' if css_class else ""
    return f'<a href="{_e(url)}" target="_blank" rel="noopener noreferrer"{cls}>{_e(text)}</a>'


def detail_header(eyebrow: str, title: str, subtitle: str = "", badges: Sequence[str] = ()) -> None:
    sub = f'<div class="q-dhead-sub">{_e(subtitle)}</div>' if subtitle else ""
    chips = f'<div class="q-badges">{"".join(badges)}</div>' if badges else ""
    _render(f'<div class="q-dialog q-dhead"><div class="q-dhead-eyebrow">{_e(eyebrow)}</div>'
            f'<div class="q-dhead-title">{_e(title)}</div>{sub}{chips}</div>')


def detail_title(text: str) -> None:
    """Small uppercase heading between popup sections."""
    _render(f'<div class="q-dcard-title" style="margin:18px 0 2px">{_e(text)}</div>')


@dataclass(frozen=True)
class Field:
    label: str
    value: str = ""
    html: str = ""   # pre-built HTML (e.g. a link); used instead of `value` when given


def detail_card(title: str, fields: Sequence[Field]) -> None:
    """Card with label / value rows stacked top to bottom (no sideways scrolling)."""
    rows = []
    for item in fields:
        text = str(item.value or "").strip()
        if item.html:
            value = f'<div class="q-field-value">{item.html}</div>'
        elif text:
            value = f'<div class="q-field-value">{_e(text)}</div>'
        else:
            value = '<div class="q-field-value is-empty">—</div>'
        rows.append(f'<div class="q-field"><div class="q-field-label">{_e(item.label)}</div>{value}</div>')
    _render(f'<div class="q-dialog q-dcard"><div class="q-dcard-title">{_e(title)}</div>{"".join(rows)}</div>')


@dataclass(frozen=True)
class Person:
    name: str
    subtitle: str = ""
    whatsapp_url: str = ""
    contact_text: str = ""


def people_card(title: str, people: Sequence[Person], empty_text: str = "Nobody recorded yet.") -> None:
    rows = []
    for person in people:
        initials = "".join(part[0] for part in person.name.split()[:2]).upper() or "?"
        contact = (link(person.whatsapp_url, f"WhatsApp {person.contact_text}".strip(), "q-wa")
                   if person.whatsapp_url else
                   f'<span class="q-person-sub">{_e(person.contact_text or "No contact")}</span>')
        rows.append(
            f'<div class="q-person"><div class="q-avatar">{_e(initials)}</div>'
            f'<div class="q-person-main"><div class="q-person-name">{_e(person.name)}</div>'
            f'<div class="q-person-sub">{_e(person.subtitle)}</div></div>{contact}</div>'
        )
    body = "".join(rows) or f'<div class="q-note">{_e(empty_text)}</div>'
    _render(f'<div class="q-dialog q-dcard"><div class="q-dcard-title">{_e(title)}</div>{body}</div>')


def progress(done: int, total: int, left_text: str, right_text: str = "") -> None:
    share = 0 if not total else round(100 * done / total)
    _render(f'<div class="q-progress"><span style="width:{share}%"></span></div>'
            f'<div class="q-progress-text"><span>{_e(left_text)}</span><span>{_e(right_text)}</span></div>')


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


def splash_html(title: str, subtitle: str = "", css_class: str = "") -> str:
    """Full-screen loading screen (logo, title, moving bar) that covers the page while it is busy."""
    sub = f'<div class="q-splash-sub">{_e(subtitle)}</div>' if subtitle else ""
    return (f'<div class="q-splash {css_class}" role="status" aria-live="polite"><div class="q-logo">Q</div>'
            f'<div class="q-splash-title">{_e(title)}</div>{sub}'
            f'<div class="q-splash-bar"><span></span></div></div>')


def login_footer() -> None:
    _render(
        '<div class="q-login-foot">Access is limited to authorised procurement staff.<br>'
        'Need an account? Ask your administrator.</div>'
    )


def fmt_int(value) -> str:
    """12345 -> '12,345'."""
    return f"{int(value):,}"
