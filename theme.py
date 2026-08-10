"""
Party Check-In System — Design System

Convention: every component builder below RETURNS an html string. The caller
is responsible for rendering it, e.g.:

    st.markdown(theme.hero(), unsafe_allow_html=True)

The one exception is `inject_css()`, which is a page-setup call rather than a
component — it writes the consolidated <style> block directly via
`st.markdown(..., unsafe_allow_html=True)` and returns None.

All dynamic text passed into these builders is run through `html.escape()`
before interpolation, since callers may pass guest names, emails, Zelle refs,
or other secret-derived config values (e.g. `config.zelle_info()`) into them.
"""

import html

import streamlit as st

import config

# Series color for st.bar_chart / st.line_chart, kept in step with --gold
# so charts match the rest of the palette instead of Streamlit default blue.
CHART_COLOR = "#D4AF37"

# ── Design tokens + consolidated stylesheet ─────────────────────────────────

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');

:root {
    /* Color tokens */
    --gold: #D4AF37;
    --gold-rgb: 212, 175, 55;
    --gold-soft: #F4E4BC;
    --gold-soft-rgb: 244, 228, 188;
    --gold-dark: #B8860B;
    --violet: #8A2BE2;
    --violet-rgb: 138, 43, 226;
    --cyan: #00C9FF;
    --cyan-rgb: 0, 201, 255;
    --mint: #92FE9D;

    --ink: #0a0a0a;
    --surface: #141414;
    --surface-2: #1a0a1a;
    --elevated: rgba(255, 255, 255, 0.04);
    --elevated-strong: rgba(255, 255, 255, 0.08);
    --border: rgba(255, 255, 255, 0.08);
    --border-strong: rgba(255, 255, 255, 0.15);

    --text: #F5F5F5;
    --text-rgb: 245, 245, 245;
    --text-dim: rgba(245, 245, 245, 0.65);
    --text-dimmer: rgba(245, 245, 245, 0.45);

    --ok: #22C55E;
    --ok-rgb: 34, 197, 94;
    --ok-bg: rgba(34, 197, 94, 0.12);
    --ok-border: rgba(34, 197, 94, 0.3);

    --warn: #F59E0B;
    --warn-rgb: 245, 158, 11;
    --warn-bg: rgba(245, 158, 11, 0.12);
    --warn-border: rgba(245, 158, 11, 0.3);

    --err: #FF6B6B;
    --err-rgb: 255, 107, 107;
    --err-bg: rgba(255, 107, 107, 0.12);
    --err-border: rgba(255, 107, 107, 0.3);

    --info: #3B82F6;
    --info-rgb: 59, 130, 246;
    --info-bg: rgba(59, 130, 246, 0.12);
    --info-border: rgba(59, 130, 246, 0.3);

    /* Radii */
    --radius-sm: 8px;
    --radius-md: 12px;
    --radius-lg: 16px;
    --radius-xl: 20px;
    --radius-pill: 999px;

    /* Shadows */
    --shadow-sm: 0 4px 14px rgba(0, 0, 0, 0.25);
    --shadow-md: 0 8px 32px rgba(0, 0, 0, 0.35);
    --shadow-lg: 0 10px 40px rgba(0, 0, 0, 0.5);
    --shadow-gold: 0 4px 14px rgba(var(--gold-rgb), 0.25);
    --shadow-gold-lg: 0 0 30px rgba(var(--gold-rgb), 0.2);

    /* Spacing scale */
    --space-1: 4px;
    --space-2: 8px;
    --space-3: 12px;
    --space-4: 16px;
    --space-5: 20px;
    --space-6: 24px;
    --space-8: 32px;
}

/* ── Base typography & background ─────────────────────────────────────── */
html, body, [class*="css"] {
    font-family: 'Inter', sans-serif !important;
}

.stApp {
    background: linear-gradient(135deg, var(--ink) 0%, var(--surface) 50%, var(--surface-2) 100%) !important;
}

h1, h2, h3 {
    color: var(--text) !important;
    font-weight: 700 !important;
}
/* Page titles come from st.title("<emoji> Text") — a single text node mixing
   a color-emoji glyph with plain text. Gradient text via background-clip:text
   + transparent fill does not compose with color-emoji glyphs in Chromium/
   WebKit: the emoji paints as a solid opaque box in the fill color instead of
   its real glyph. Custom HTML titles (theme.hero(), which puts its emoji and
   text in a <div>, not a bare <h1>) are unaffected and keep the full gradient
   treatment. Bare h1 (Streamlit's st.title output) gets a flat gold instead
   so its emoji renders correctly. */
h1 {
    color: var(--gold) !important;
}

#MainMenu {visibility: hidden;}
header {visibility: hidden;}
footer {visibility: hidden;}

/* ── Layout / overflow safety ─────────────────────────────────────────── */
html, body {
    overflow-x: hidden !important;
}
.block-container {
    padding: var(--space-6) var(--space-3) var(--space-8) var(--space-3) !important;
    max-width: 100% !important;
    width: 100% !important;
    overflow-x: hidden !important;
}

@media (min-width: 768px) {
    .block-container {
        max-width: 760px !important;
        margin-left: auto !important;
        margin-right: auto !important;
        padding-left: var(--space-5) !important;
        padding-right: var(--space-5) !important;
    }
}

@media (min-width: 1200px) {
    .block-container {
        max-width: 1080px !important;
    }
}

img, pre, code {
    max-width: 100% !important;
}

/* ── Focus rings — keyboard accessibility ─────────────────────────────── */
:focus-visible {
    outline: 3px solid var(--cyan) !important;
    outline-offset: 2px !important;
    border-radius: 6px !important;
}
button:focus-visible,
.stButton > button:focus-visible,
a:focus-visible,
input:focus-visible,
textarea:focus-visible,
select:focus-visible,
[role="radio"]:focus-visible,
[role="checkbox"]:focus-visible,
[tabindex]:focus-visible {
    outline: 3px solid var(--cyan) !important;
    outline-offset: 2px !important;
}

/* ── Motion — only for users who don't prefer reduced motion ──────────── */
@media (prefers-reduced-motion: no-preference) {
    button, .stButton > button {
        transition: transform 0.15s ease, box-shadow 0.15s ease !important;
    }
    button:hover:not([role="tab"]):not([data-testid="stBaseButton-headerNoPadding"]),
    .stButton > button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 20px rgba(var(--gold-rgb), 0.4) !important;
    }
    .nav-card {
        transition: background 0.2s ease, border-color 0.2s ease, transform 0.2s ease !important;
    }
    .nav-card:hover {
        transform: translateY(-2px) !important;
    }
}

/* ── Buttons ───────────────────────────────────────────────────────────── */
/* Excludes Streamlit's own tab controls (button[role="tab"] / [data-baseweb="tab"])
   and the sidebar collapse/expand toggle (data-testid="stBaseButton-headerNoPadding") —
   both are plain <button> elements that would otherwise pick up this gold treatment
   too. They get their own dedicated styling further down. */
button:not([role="tab"]):not([data-testid="stBaseButton-headerNoPadding"]),
.stButton > button {
    min-height: 48px !important;
    font-size: 1.05rem !important;
    font-weight: 700 !important;
    border-radius: var(--radius-md) !important;
    background: linear-gradient(90deg, var(--gold) 0%, var(--gold-dark) 100%) !important;
    color: var(--ink) !important;
    border: none !important;
    box-shadow: var(--shadow-gold) !important;
}
button[kind="secondary"], .stButton > button[kind="secondary"] {
    background: var(--elevated-strong) !important;
    color: var(--text) !important;
    border: 1px solid var(--border-strong) !important;
    box-shadow: none !important;
}
.stDownloadButton > button {
    min-height: 48px !important;
    border-radius: var(--radius-md) !important;
}

/* ── Inputs: dark glass ────────────────────────────────────────────────── */
input, .stTextInput > div > div > input, .stNumberInput > div > div > input,
.stSelectbox > div > div, .stTextArea > div > div > textarea {
    font-size: 1.05rem !important;
    min-height: 48px !important;
    background: var(--elevated-strong) !important;
    color: var(--text) !important;
    border: 1px solid var(--border-strong) !important;
    border-radius: var(--radius-md) !important;
}
input::placeholder, .stTextInput > div > div > input::placeholder {
    color: var(--text-dimmer) !important;
}

/* ── Cards / containers: glassmorphism ────────────────────────────────── */
div[data-testid="stContainer"] {
    border-radius: var(--radius-lg) !important;
    background: var(--elevated) !important;
    border: 1px solid var(--border) !important;
    box-shadow: var(--shadow-md) !important;
}

/* ── Sticky brand bar ──────────────────────────────────────────────────── */
.brand-bar {
    position: sticky;
    top: 0;
    z-index: 999;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-3);
    padding: 10px var(--space-4);
    margin: 0 0 var(--space-5) 0;
    background: rgba(10, 10, 10, 0.92);
    backdrop-filter: blur(10px);
    -webkit-backdrop-filter: blur(10px);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
}
.brand-bar-title {
    font-weight: 800;
    font-size: 0.95rem;
    color: var(--gold-soft);
    display: flex;
    align-items: center;
    gap: 8px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    min-width: 0;
}

/* Streamlit renders a fixed sidebar-toggle chevron over the top-left corner
   when the sidebar is collapsed. On narrow viewports the block-container has
   little side padding, so the brand bar needs extra left clearance to avoid
   the title text rendering underneath that control. */
@media (max-width: 767px) {
    .brand-bar {
        padding-left: 52px;
    }
}

/* ── Sidebar collapse / expand controls ───────────────────────────────────
   Streamlit's built-in chevron (collapsed state, floats top-left) and the
   "×" close control (expanded state, inside the sidebar header) are plain
   <button> elements. Give them a subtle ghost treatment instead of the
   gold gradient the general button rule would otherwise apply — they're
   chrome, not calls to action. */
[data-testid="stSidebarCollapsedControl"] button,
[data-testid="stSidebarCollapseButton"] button {
    background: transparent !important;
    color: var(--text-dim) !important;
    border: 1px solid var(--border-strong) !important;
    box-shadow: none !important;
    min-height: 40px !important;
    min-width: 40px !important;
}
[data-testid="stSidebarCollapsedControl"] button:hover,
[data-testid="stSidebarCollapseButton"] button:hover {
    background: var(--elevated) !important;
    color: var(--gold-soft) !important;
    border-color: rgba(var(--gold-rgb), 0.35) !important;
    box-shadow: none !important;
    transform: none !important;
}

/* ── Pills / badges ────────────────────────────────────────────────────── */
.pill, .badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: rgba(0, 0, 0, 0.4);
    border: 1px solid rgba(var(--gold-rgb), 0.5);
    border-radius: var(--radius-pill);
    padding: 6px 14px;
    margin: 4px 4px 0 0;
    color: var(--text);
    font-size: 0.85rem;
    font-weight: 600;
    white-space: nowrap;
    max-width: 100%;
}
.badge-wide {
    white-space: normal;
}
.pill-countdown {
    border-color: rgba(var(--cyan-rgb), 0.55);
    color: var(--gold-soft);
}

/* ── Hero banner ───────────────────────────────────────────────────────── */
.hero-banner {
    background: linear-gradient(135deg, rgba(var(--gold-rgb), 0.15) 0%, rgba(var(--violet-rgb), 0.12) 100%);
    border: 1px solid rgba(var(--gold-rgb), 0.35);
    border-radius: var(--radius-xl);
    padding: var(--space-6) var(--space-5);
    text-align: center;
    box-shadow: var(--shadow-gold-lg);
    margin-bottom: var(--space-5);
}
.hero-title {
    font-size: 2.2rem;
    font-weight: 800;
    margin: 0 0 6px 0;
    background: linear-gradient(90deg, var(--gold) 0%, var(--gold-soft) 50%, var(--gold) 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    letter-spacing: -0.5px;
    line-height: 1.2;
}
.hero-subtitle {
    font-size: 1.1rem;
    color: var(--gold-soft);
    font-weight: 600;
    margin-bottom: var(--space-3);
}
.hero-badges {
    display: flex;
    flex-wrap: wrap;
    justify-content: center;
    gap: 0;
}

@media (max-width: 640px) {
    .hero-title { font-size: 1.7rem !important; }
    .hero-subtitle { font-size: 0.95rem !important; }
}

/* ── Section header ────────────────────────────────────────────────────── */
.section-header {
    margin: var(--space-6) 0 var(--space-3) 0;
}
.section-header h3 {
    margin: 0 !important;
    font-size: 1.2rem !important;
}
.section-subtitle {
    color: var(--text-dim);
    font-size: 0.88rem;
    margin: 2px 0 0 0;
}

/* ── Stat tile grid ────────────────────────────────────────────────────── */
/* auto-fill (not auto-fit) so every stat_tiles() call gets the same track
   width regardless of how many tiles are in the group — a 2-tile row (e.g.
   "Traffic") keeps the same tile width as a 6- or 9-tile row above it
   instead of its tracks stretching to fill the leftover space. */
.stat-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
    gap: var(--space-3);
    margin: var(--space-3) 0 var(--space-5) 0;
}
.stat-tile {
    display: flex;
    flex-direction: column;
    background: var(--elevated);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    padding: var(--space-4) var(--space-5);
    box-shadow: var(--shadow-md);
    min-width: 0;
}
.stat-label {
    font-size: 0.72rem;
    line-height: 1.3;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--text-dim);
    margin-bottom: 4px;
    /* Reserve room for a two-line label so the value below always starts at
       the same height, whether this tile's label wraps or not. */
    min-height: 2.6em;
    overflow-wrap: break-word;
}
.stat-value {
    font-size: 1.8rem;
    font-weight: 800;
    color: var(--gold-soft);
    line-height: 1.15;
    overflow-wrap: break-word;
    /* Bottom-align the value (and caption, if any) within the tile so every
       value in a row sits on the same baseline even when tiles are
       grid-stretched to the row's tallest neighbor. */
    margin-top: auto;
}
.stat-caption {
    font-size: 0.78rem;
    color: var(--text-dimmer);
    margin-top: 4px;
}

/* ── Nav cards ─────────────────────────────────────────────────────────── */
.nav-card {
    background: var(--elevated);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    padding: var(--space-5);
}
.nav-card:hover {
    background: rgba(var(--gold-rgb), 0.08);
    border-color: rgba(var(--gold-rgb), 0.3);
}
.nav-card h3 {
    color: var(--gold-soft) !important;
    margin: 0 0 6px 0 !important;
    font-size: 1.1rem !important;
}
.nav-card p {
    color: var(--text-dim);
    margin: 0 !important;
    font-size: 0.92rem !important;
}

/* ── Payment card ──────────────────────────────────────────────────────── */
.payment-card {
    background: linear-gradient(135deg, var(--surface) 0%, #0d0d0d 100%);
    border: 1px solid rgba(var(--gold-rgb), 0.4);
    border-radius: var(--radius-xl);
    padding: var(--space-6);
    box-shadow: var(--shadow-lg);
    position: relative;
    overflow: hidden;
}
.payment-card::before {
    content: "";
    position: absolute;
    top: 0; left: 0; right: 0; height: 4px;
    background: linear-gradient(90deg, var(--gold), var(--violet), var(--cyan));
}
.payment-card-head {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: var(--space-3);
}
.payment-icon { font-size: 1.8rem; }
.payment-title { font-size: 1.15rem; font-weight: 700; color: var(--gold-soft); }
.payment-desc {
    color: var(--text-dim);
    margin: 0 0 var(--space-4) 0;
}
.zelle-box {
    background: rgba(0, 0, 0, 0.35);
    border-radius: var(--radius-md);
    padding: var(--space-4);
    margin-bottom: var(--space-4);
    border: 1px solid rgba(var(--gold-rgb), 0.25);
}
.zelle-label {
    font-size: 0.78rem;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: var(--gold);
    margin-bottom: 4px;
}
.zelle-email {
    font-size: 1.15rem;
    font-weight: 700;
    color: var(--gold-soft);
    letter-spacing: 0.3px;
    word-break: break-all;
}
.payment-price-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    color: var(--text-dim);
}
.price-tag {
    font-size: 1.8rem;
    font-weight: 800;
    color: var(--gold);
}

/* ── Total-to-pay card ─────────────────────────────────────────────────── */
.total-card {
    background: linear-gradient(135deg, rgba(var(--gold-rgb), 0.25) 0%, rgba(var(--violet-rgb), 0.15) 100%);
    border: 1px solid rgba(var(--gold-rgb), 0.35);
    color: var(--text);
    padding: var(--space-5);
    border-radius: var(--radius-lg);
    text-align: center;
    margin: var(--space-4) 0;
}
.total-label {
    font-size: 0.82rem;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: var(--gold);
}
.total-value {
    font-size: 2.2rem;
    font-weight: 800;
    color: var(--gold);
    line-height: 1.2;
}
.total-caption {
    font-size: 0.88rem;
    color: var(--text-dim);
}

/* ── Stepper ───────────────────────────────────────────────────────────── */
.stepper {
    display: flex;
    align-items: center;
    justify-content: center;
    flex-wrap: wrap;
    gap: var(--space-2);
    margin: 0 0 var(--space-5) 0;
}
.step {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 12px;
    border-radius: var(--radius-pill);
    border: 1px solid var(--border);
    background: var(--elevated);
    font-size: 0.85rem;
    color: var(--text-dimmer);
}
.step-num {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 20px;
    height: 20px;
    border-radius: 50%;
    background: var(--elevated-strong);
    font-size: 0.75rem;
    font-weight: 700;
    color: var(--text-dim);
}
.step-active {
    border-color: rgba(var(--gold-rgb), 0.5);
    color: var(--gold-soft);
}
.step-active .step-num {
    background: var(--gold);
    color: var(--ink);
}
.step-done {
    color: var(--ok);
}
.step-done .step-num {
    background: var(--ok);
    color: var(--ink);
}

/* ── Field error ───────────────────────────────────────────────────────── */
.field-error {
    color: var(--err) !important;
    font-size: 0.85rem !important;
    margin: 2px 0 var(--space-3) 0 !important;
}

/* ── Validation banner (registration form) ────────────────────────────── */
.validation-banner {
    display: flex;
    align-items: center;
    gap: 10px;
    background: var(--err-bg);
    border: 1px solid var(--err-border);
    border-radius: var(--radius-md);
    padding: var(--space-4) var(--space-5);
    color: var(--text);
    font-weight: 700;
    font-size: 0.98rem;
    margin: 0 0 var(--space-4) 0;
}

/* ── Closed notice (scanner page, check-in not open yet) ──────────────── */
.closed-notice {
    text-align: center;
    background: var(--info-bg);
    border: 1px solid var(--info-border);
    border-radius: var(--radius-lg);
    padding: var(--space-6) var(--space-5);
    margin: var(--space-4) 0;
}
.closed-notice-icon { font-size: 2.2rem; margin-bottom: 8px; }
.closed-notice-title {
    font-size: 1.15rem;
    font-weight: 800;
    color: var(--text);
    margin-bottom: 6px;
}
.closed-notice-message { color: var(--text-dim); font-size: 0.95rem; }

/* ── Check-in window status banner (admin) ────────────────────────────── */
.checkin-window-banner {
    display: flex;
    align-items: center;
    gap: 10px;
    border-radius: var(--radius-lg);
    padding: var(--space-4) var(--space-5);
    margin: var(--space-3) 0 var(--space-4) 0;
    font-size: 1.02rem;
    border: 1px solid var(--border);
}
.checkin-window-banner.status-ok {
    background: var(--ok-bg);
    border-color: var(--ok-border);
    color: var(--text);
}
.checkin-window-banner.status-warn {
    background: var(--warn-bg);
    border-color: var(--warn-border);
    color: var(--text);
}
.checkin-window-icon { font-size: 1.4rem; }

/* ── Guest result card (scanner) ──────────────────────────────────────── */
.guest-result-card {
    border-radius: var(--radius-lg);
    padding: var(--space-5);
    margin: var(--space-4) 0;
    border: 1px solid var(--border);
}
.guest-result-card.status-ok { background: var(--ok-bg); border-color: var(--ok-border); }
.guest-result-card.status-warn { background: var(--warn-bg); border-color: var(--warn-border); }
.guest-result-card.status-err { background: var(--err-bg); border-color: var(--err-border); }
.guest-result-name { font-size: 1.3rem; font-weight: 800; color: var(--text); }
.guest-result-meta { color: var(--text-dim); margin: 2px 0 8px 0; }
.guest-result-status { font-weight: 700; }
.status-ok .guest-result-status { color: var(--ok); }
.status-warn .guest-result-status { color: var(--warn); }
.status-err .guest-result-status { color: var(--err); }
.guest-result-message { margin-top: 8px; color: var(--text-dim); font-size: 0.9rem; }

/* ── Footer ────────────────────────────────────────────────────────────── */
.app-footer {
    text-align: center;
    opacity: 0.5;
    font-size: 0.8em;
    margin-top: var(--space-6);
}

/* ── QR code image ─────────────────────────────────────────────────────── */
/* st.image() doesn't expose a way to set meaningful alt text (it defaults
   to the image's index, e.g. alt="0"), so target Streamlit's own image
   wrapper instead of alt text. This app only ever renders QR codes via
   st.image, so scoping to stImage is safe and specific enough. */
div[data-testid="stImage"] img {
    max-width: 100% !important;
    width: 320px !important;
    border-radius: var(--radius-lg) !important;
    box-shadow: var(--shadow-gold-lg) !important;
}

/* ── Alerts ────────────────────────────────────────────────────────────── */
.stAlert {
    border-radius: var(--radius-md) !important;
}
.stSuccess {
    background: var(--ok-bg) !important;
    border: 1px solid var(--ok-border) !important;
}
.stInfo {
    background: var(--info-bg) !important;
    border: 1px solid var(--info-border) !important;
}
.stWarning {
    background: var(--warn-bg) !important;
    border: 1px solid var(--warn-border) !important;
}
.stError {
    background: var(--err-bg) !important;
    border: 1px solid var(--err-border) !important;
}

/* ── Tabs ──────────────────────────────────────────────────────────────── */
/* Transparent/ghost tabs: muted text when inactive, gold text + gold
   underline when active. The tab list scrolls horizontally on narrow
   viewports instead of squashing labels. */
.stTabs [data-baseweb="tab-list"] {
    gap: var(--space-1);
    background: transparent !important;
    overflow-x: auto;
    overflow-y: hidden;
    flex-wrap: nowrap !important;
    -webkit-overflow-scrolling: touch;
    scrollbar-width: thin;
}
.stTabs [data-baseweb="tab-list"]::-webkit-scrollbar {
    height: 4px;
}
.stTabs button[role="tab"],
.stTabs [data-baseweb="tab"] {
    background: transparent !important;
    color: var(--text-dim) !important;
    border: none !important;
    border-bottom: 3px solid transparent !important;
    border-radius: 0 !important;
    box-shadow: none !important;
    padding: 10px var(--space-4) !important;
    margin: 0 !important;
    min-height: auto !important;
    font-size: 0.95rem !important;
    font-weight: 600 !important;
    white-space: nowrap !important;
    flex-shrink: 0 !important;
}
.stTabs button[role="tab"]:hover,
.stTabs [data-baseweb="tab"]:hover {
    color: var(--gold-soft) !important;
    background: rgba(var(--gold-rgb), 0.08) !important;
}
.stTabs button[role="tab"][aria-selected="true"],
.stTabs [data-baseweb="tab"][aria-selected="true"] {
    color: var(--gold) !important;
    font-weight: 700 !important;
    border-bottom-color: var(--gold) !important;
    background: transparent !important;
}
/* BaseWeb's own sliding highlight bar — we draw the underline per-tab above
   instead, so neutralize this to avoid a second, out-of-sync indicator. */
.stTabs [data-baseweb="tab-highlight"] {
    background: transparent !important;
}
.stTabs [data-baseweb="tab-border"] {
    background: var(--border) !important;
}

/* ── Mobile: wide content scrolls in its own box, never the page ─────────── */
div[data-testid="stDataFrame"], div[data-testid="stTable"] {
    overflow-x: auto !important;
    max-width: 100% !important;
}

@media (max-width: 480px) {
    .block-container {
        padding: var(--space-5) var(--space-2) var(--space-6) var(--space-2) !important;
    }
    .brand-bar-title { font-size: 0.85rem; }
    button:not([role="tab"]):not([data-testid="stBaseButton-headerNoPadding"]),
    .stButton > button {
        min-height: 48px !important;
        width: 100%;
    }
}
</style>
"""


def inject_css() -> None:
    """Render the consolidated design-system stylesheet. Call once per page load."""
    st.markdown(_CSS, unsafe_allow_html=True)


# ── Component builders ───────────────────────────────────────────────────────

def countdown_pill() -> str:
    """A small pill showing days remaining until the event, via config.days_until_event()."""
    days = config.days_until_event()
    if days <= 0:
        label = "It's happening!"
    elif days == 1:
        label = "1 day to go"
    else:
        label = f"{days} days to go"
    return f'<span class="pill pill-countdown">⏳ {html.escape(label)}</span>'


def brand_bar() -> str:
    """Slim sticky bar with the event name and a countdown pill. Renders once per page."""
    return (
        '<div class="brand-bar">'
        f'<div class="brand-bar-title">🎉 {html.escape(config.EVENT_NAME)}</div>'
        f'{countdown_pill()}'
        '</div>'
    )


def hero() -> str:
    """The homepage hero banner: title, tagline, and a date/time/venue badge row.

    The countdown itself lives only in the sticky brand bar (always visible
    while scrolling) — it's intentionally not repeated here to avoid showing
    it twice on the same page.
    """
    return f"""
    <div class="hero-banner">
        <div class="hero-title">🎉 {html.escape(config.EVENT_NAME)}</div>
        <div class="hero-subtitle">{html.escape(config.EVENT_TAGLINE)}</div>
        <div class="hero-badges">
            <span class="badge">📅 {html.escape(config.EVENT_DATE_TEXT)}</span>
            <span class="badge">🕕 {html.escape(config.EVENT_TIME_TEXT)}</span>
        </div>
        <div class="hero-badges">
            <span class="badge badge-wide">📍 {html.escape(config.VENUE_NAME)}, {html.escape(config.VENUE_ADDRESS)}</span>
        </div>
    </div>
    """


def stat_tiles(items: list) -> str:
    """A responsive CSS-grid of stat tiles.

    `items` is a list of (label, value, caption) tuples. `caption` may be
    empty/None to omit the caption line.
    """
    tiles = []
    for label, value, caption in items:
        cap_html = (
            f'<div class="stat-caption">{html.escape(str(caption))}</div>' if caption else ""
        )
        tiles.append(
            f'<div class="stat-tile">'
            f'<div class="stat-label">{html.escape(str(label))}</div>'
            f'<div class="stat-value">{html.escape(str(value))}</div>'
            f'{cap_html}'
            f'</div>'
        )
    return f'<div class="stat-grid">{"".join(tiles)}</div>'


def section_header(title: str, subtitle: str = "") -> str:
    """A section heading with an optional dimmer subtitle line beneath it."""
    sub_html = f'<p class="section-subtitle">{html.escape(subtitle)}</p>' if subtitle else ""
    return f'<div class="section-header"><h3>{html.escape(title)}</h3>{sub_html}</div>'


def nav_card(icon: str, title: str, desc: str) -> str:
    """The card body for a home-page navigation tile. Pair with an st.button below it."""
    return (
        '<div class="nav-card">'
        f'<h3>{html.escape(icon)} {html.escape(title)}</h3>'
        f'<p>{html.escape(desc)}</p>'
        '</div>'
    )


def payment_card(zelle_info: str, price: float) -> str:
    """The Zelle payment instructions card shown on the Register page."""
    return f"""
    <div class="payment-card">
        <div class="payment-card-head">
            <span class="payment-icon">💳</span>
            <span class="payment-title">Step 1: Pay via Zelle</span>
        </div>
        <p class="payment-desc">
            Before registering, send your payment via Zelle in your banking app.
            You'll need the <strong>transaction confirmation number</strong> on the next step.
        </p>
        <div class="zelle-box">
            <div class="zelle-label">Send Zelle To</div>
            <div class="zelle-email">{html.escape(zelle_info)}</div>
        </div>
        <div class="payment-price-row">
            <span>Price per ticket</span>
            <span class="price-tag">${price:.2f}</span>
        </div>
    </div>
    """


def total_card(tickets: int, price: float) -> str:
    """The live-updating 'Total to Pay' card on the Register page."""
    tickets = int(tickets)
    total = tickets * price
    plural = "s" if tickets != 1 else ""
    return f"""
    <div class="total-card">
        <div class="total-label">Total to Pay</div>
        <div class="total-value">${total:,.2f}</div>
        <div class="total-caption">{tickets} ticket{plural} × ${price:.2f}</div>
    </div>
    """


def stepper(current_step: int, steps: list = None) -> str:
    """A horizontal progress stepper. `current_step` is 1-indexed."""
    steps = steps or ["Pay via Zelle", "Your Details", "Confirmation"]
    parts = []
    for i, label in enumerate(steps, start=1):
        if i < current_step:
            state = "step-done"
        elif i == current_step:
            state = "step-active"
        else:
            state = ""
        parts.append(
            f'<div class="step {state}">'
            f'<span class="step-num">{i}</span>'
            f'<span class="step-label">{html.escape(label)}</span>'
            f'</div>'
        )
    return f'<div class="stepper">{"".join(parts)}</div>'


def field_error(msg: str) -> str:
    """A small error line meant to render directly under a form field."""
    return f'<p class="field-error">⚠ {html.escape(msg)}</p>'


def validation_banner(error_count: int) -> str:
    """An error banner shown above the registration form when validation fails.

    `error_count` is len(errors) from utils.validate_registration — used to
    pluralize "field(s)" correctly. Per-field messages still render under
    each field via field_error(); this banner is the at-a-glance summary.
    """
    error_count = int(error_count)
    field_word = "field" if error_count == 1 else "fields"
    return (
        '<div class="validation-banner">'
        f'⚠️ Couldn’t submit — please fix the {error_count} highlighted {field_word} below.'
        '</div>'
    )


def closed_notice(message: str) -> str:
    """A friendly notice shown on the Scanner page when check-in isn't open yet.

    Replaces the camera + manual-entry inputs entirely (there's nothing
    useful for a guest to do with them while the window is closed).
    """
    return f"""
    <div class="closed-notice">
        <div class="closed-notice-icon">🕒</div>
        <div class="closed-notice-title">Check-in isn't open yet</div>
        <div class="closed-notice-message">{html.escape(message)}</div>
    </div>
    """


def checkin_window_banner(is_open: bool, detail: str = "") -> str:
    """A prominent banner showing the current check-in gate status (admin)."""
    css_class = "status-ok" if is_open else "status-warn"
    icon = "🟢" if is_open else "🔒"
    label = "OPEN" if is_open else "CLOSED"
    detail_html = f" — {html.escape(detail)}" if detail else ""
    return (
        f'<div class="checkin-window-banner {css_class}">'
        f'<span class="checkin-window-icon">{icon}</span>'
        f'<span>Check-in is <strong>{label}</strong>{detail_html}</span>'
        '</div>'
    )


def footer() -> str:
    """The small centered app footer line."""
    return (
        '<p class="app-footer">'
        f'{html.escape(config.EVENT_NAME)} {config.EVENT_DATE.year} • '
        f'{html.escape(config.EVENT_TAGLINE)} • v{html.escape(config.APP_VERSION)}'
        '</p>'
    )


def guest_result_card(name: str, tickets, status: str, message: str = "") -> str:
    """A result card for scanner check-ins.

    `status` is one of "success", "already", "error" — mapped to ok/warn/err
    styling and a status label. `tickets` may be None when no guest was found.
    """
    status_map = {
        "success": ("status-ok", "✅ Checked In"),
        "already": ("status-warn", "⚠ Already Checked In"),
        "error": ("status-err", "❌ Not Found"),
    }
    css_class, label = status_map.get(status, ("status-ok", html.escape(status)))

    # Built via concatenation (not a multi-line f-string) so that an empty
    # optional piece (tickets=None, message="") never leaves a blank line in
    # the middle of the output. st.markdown's HTML-block parsing treats a
    # blank line as the end of the block, which would dump everything after
    # it back out as a literal, unrendered code block.
    parts = [f'<div class="guest-result-card {css_class}">']
    parts.append(f'<div class="guest-result-name">{html.escape(str(name))}</div>')
    if tickets is not None:
        tickets = int(tickets)
        plural = "s" if tickets != 1 else ""
        parts.append(f'<div class="guest-result-meta">{tickets} ticket{plural}</div>')
    parts.append(f'<div class="guest-result-status">{label}</div>')
    if message:
        parts.append(f'<div class="guest-result-message">{html.escape(message)}</div>')
    parts.append("</div>")
    return "".join(parts)
