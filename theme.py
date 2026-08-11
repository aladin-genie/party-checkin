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
/* Disabled buttons (e.g. the Danger Zone delete button before the RESET
   phrase matches) must read as visibly inert, not just refuse clicks —
   otherwise a disabled gold button looks identical to an enabled one. */
button:disabled, .stButton > button:disabled,
button[disabled], .stButton > button[disabled] {
    opacity: 0.4 !important;
    cursor: not-allowed !important;
    box-shadow: none !important;
    transform: none !important;
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
    position: relative;
    overflow: hidden; /* clip the ::before accent bar to the tile's rounded corners */
    display: flex;
    flex-direction: column;
    background: var(--elevated);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    padding: var(--space-4) var(--space-5);
    box-shadow: var(--shadow-md);
    min-width: 0;
}
/* Every tile gets a top-edge accent bar — neutral by default, colored per
   `accent` for tiles that opt in (see theme.stat_tiles()). Gives each stat
   a bit of identity instead of a uniform grid of flat grey boxes. */
.stat-tile::before {
    content: "";
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 3px;
    background: var(--border-strong);
}
.stat-tile.accent-gold::before { background: linear-gradient(90deg, var(--gold-dark), var(--gold)); }
.stat-tile.accent-ok::before { background: var(--ok); }
.stat-tile.accent-warn::before { background: var(--warn); }
.stat-tile.accent-err::before { background: var(--err); }
.stat-tile.accent-info::before { background: var(--info); }
.stat-tile.accent-violet::before { background: var(--violet); }
.stat-tile.accent-cyan::before { background: var(--cyan); }

.stat-label {
    display: flex;
    align-items: center;
    gap: 6px;
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
.stat-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    width: 22px;
    height: 22px;
    border-radius: 50%;
    background: var(--elevated-strong);
    font-size: 0.82rem;
    text-transform: none;
    letter-spacing: normal;
}
.stat-tile.accent-gold .stat-icon { background: rgba(var(--gold-rgb), 0.18); }
.stat-tile.accent-ok .stat-icon { background: var(--ok-bg); }
.stat-tile.accent-warn .stat-icon { background: var(--warn-bg); }
.stat-tile.accent-err .stat-icon { background: var(--err-bg); }
.stat-tile.accent-info .stat-icon { background: var(--info-bg); }
.stat-tile.accent-violet .stat-icon { background: rgba(var(--violet-rgb), 0.18); }
.stat-tile.accent-cyan .stat-icon { background: rgba(var(--cyan-rgb), 0.18); }

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
.stat-tile.accent-ok .stat-value { color: var(--ok); }
.stat-tile.accent-warn .stat-value { color: var(--warn); }
.stat-tile.accent-err .stat-value { color: var(--err); }
.stat-tile.accent-info .stat-value { color: var(--info); }
.stat-tile.accent-violet .stat-value { color: var(--violet); }
.stat-tile.accent-cyan .stat-value { color: var(--cyan); }

.stat-caption {
    font-size: 0.78rem;
    color: var(--text-dimmer);
    margin-top: 4px;
}

/* ── Hero stat tile ────────────────────────────────────────────────────── */
/* Reserved for the 1-2 numbers that actually matter operationally on a given
   page (e.g. Checked In / Total Guests) — bigger value, tinted wash, and it
   spans two grid tracks so it visually leads the row instead of blending
   into a uniform grid of identical boxes. */
.stat-tile-hero {
    grid-column: span 2;
    padding: var(--space-5) var(--space-6);
    border-color: var(--border-strong);
}
.stat-tile-hero .stat-label {
    font-size: 0.78rem;
    min-height: 0;
}
.stat-tile-hero .stat-icon {
    width: 26px;
    height: 26px;
    font-size: 0.95rem;
}
.stat-tile-hero .stat-value {
    font-size: 2.5rem;
}
.stat-tile-hero.accent-gold { background: linear-gradient(135deg, rgba(var(--gold-rgb), 0.16) 0%, var(--elevated) 100%); }
.stat-tile-hero.accent-ok { background: linear-gradient(135deg, rgba(var(--ok-rgb), 0.16) 0%, var(--elevated) 100%); }
.stat-tile-hero.accent-warn { background: linear-gradient(135deg, rgba(var(--warn-rgb), 0.16) 0%, var(--elevated) 100%); }
.stat-tile-hero.accent-err { background: linear-gradient(135deg, rgba(var(--err-rgb), 0.16) 0%, var(--elevated) 100%); }
.stat-tile-hero.accent-info { background: linear-gradient(135deg, rgba(var(--info-rgb), 0.16) 0%, var(--elevated) 100%); }
.stat-tile-hero.accent-violet { background: linear-gradient(135deg, rgba(var(--violet-rgb), 0.16) 0%, var(--elevated) 100%); }
.stat-tile-hero.accent-cyan { background: linear-gradient(135deg, rgba(var(--cyan-rgb), 0.16) 0%, var(--elevated) 100%); }

@media (max-width: 380px) {
    /* Even a 2-column layout gets tight under ~380px with tile padding —
       let the hero tile take the full row's single column there instead of
       forcing two 150px tracks to squeeze in. */
    .stat-tile-hero { grid-column: 1 / -1; }
}

/* ── Progress meter (real labelled progress, not a bare st.progress) ────── */
.progress-meter {
    margin: var(--space-2) 0 var(--space-5) 0;
}
.progress-meter-track {
    position: relative;
    height: 14px;
    border-radius: var(--radius-pill);
    background: var(--elevated-strong);
    border: 1px solid var(--border);
    overflow: hidden;
}
.progress-meter-fill {
    height: 100%;
    border-radius: var(--radius-pill);
    background: linear-gradient(90deg, var(--gold-dark) 0%, var(--gold) 60%, var(--gold-soft) 100%);
    box-shadow: 0 0 10px rgba(var(--gold-rgb), 0.45);
    transition: width 0.4s ease;
}
.progress-meter-detail {
    margin-top: 8px;
    font-size: 0.95rem;
    font-weight: 700;
    color: var(--text);
}

/* ── Ticket capacity (how many tickets are left to sell) ────────────────── */
/* The venue's hard cap, shown on Home and above the Register form. Reuses
   the progress-meter track shape so "how full is the party" reads the same
   way as "how many have checked in". See theme.tickets_remaining(). */
.tickets-left {
    background: var(--elevated);
    border: 1px solid var(--border);
    border-left: 3px solid var(--gold);
    border-radius: var(--radius-lg);
    padding: var(--space-4);
    margin: 0 0 var(--space-4) 0;
}
.tickets-left.is-low { border-left-color: var(--warn); }
.tickets-left.is-out { border-left-color: var(--err); }
.tickets-left-head {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: var(--space-3);
    flex-wrap: wrap;
    margin-bottom: 10px;
}
.tickets-left-count {
    font-size: 1.15rem;
    font-weight: 800;
    color: var(--gold-soft);
}
.tickets-left.is-low .tickets-left-count { color: var(--warn); }
.tickets-left.is-out .tickets-left-count { color: var(--err); }
.tickets-left-count strong { font-size: 1.5rem; }
.tickets-left-of {
    color: var(--text-dimmer);
    font-size: 0.85rem;
    font-weight: 600;
}
.tickets-left-track {
    height: 10px;
    border-radius: var(--radius-pill);
    background: var(--elevated-strong);
    border: 1px solid var(--border);
    overflow: hidden;
}
.tickets-left-fill {
    height: 100%;
    border-radius: var(--radius-pill);
    background: linear-gradient(90deg, var(--gold-dark) 0%, var(--gold) 60%, var(--gold-soft) 100%);
    transition: width 0.4s ease;
}
.tickets-left.is-low .tickets-left-fill {
    background: linear-gradient(90deg, var(--warn) 0%, var(--gold-soft) 100%);
}
.tickets-left-note {
    margin-top: 8px;
    color: var(--text-dim);
    font-size: 0.85rem;
}

/* Full-width refusal shown in place of the Register form once the cap is hit. */
.sold-out-notice {
    text-align: center;
    background: var(--err-bg);
    border: 1px solid var(--err-border);
    border-radius: var(--radius-lg);
    padding: var(--space-6) var(--space-5);
    margin: var(--space-4) 0;
}
.sold-out-icon { font-size: 2.2rem; margin-bottom: 8px; }
.sold-out-title {
    font-size: 1.25rem;
    font-weight: 800;
    color: var(--text);
    margin-bottom: 6px;
}
.sold-out-message {
    color: var(--text-dim);
    font-size: 0.95rem;
    line-height: 1.6;
    max-width: 46ch;
    margin: 0 auto;
}

/* ── Empty state ───────────────────────────────────────────────────────── */
/* A friendly placeholder for an otherwise-empty section (fresh install or
   just after an admin Danger Zone reset) so it reads as "nothing here yet",
   not "something is broken". */
.empty-state {
    text-align: center;
    padding: var(--space-6) var(--space-5);
    border: 1px dashed var(--border-strong);
    border-radius: var(--radius-lg);
    background: var(--elevated);
    margin: var(--space-3) 0 var(--space-5) 0;
}
.empty-state-icon { font-size: 2rem; margin-bottom: 6px; }
.empty-state-title {
    font-weight: 800;
    color: var(--gold-soft);
    font-size: 1.05rem;
    margin-bottom: 4px;
}
.empty-state-message {
    color: var(--text-dim);
    font-size: 0.9rem;
    max-width: 46ch;
    margin: 0 auto;
}

/* ── Danger Zone (admin) ───────────────────────────────────────────────── */
.danger-zone-warning {
    color: var(--text);
    font-size: 0.95rem;
    line-height: 1.5;
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

/* ── Guest-names requirement (how many names the ticket count needs) ───── */
/* Sits between the ticket selector and the form, and re-renders every time
   the ticket count changes, so the guest learns how many names are wanted
   before they reach the field rather than from a validation error after
   submitting. See theme.guest_names_requirement(). */
.guest-req {
    display: flex;
    align-items: center;
    gap: 10px;
    background: var(--info-bg);
    border: 1px solid var(--info-border);
    border-radius: var(--radius-md);
    padding: var(--space-3) var(--space-4);
    margin: 0 0 var(--space-4) 0;
    font-size: 0.92rem;
    color: var(--text);
}
.guest-req.is-solo {
    background: var(--elevated);
    border-color: var(--border);
    color: var(--text-dim);
}
.guest-req-icon {
    font-size: 1.1rem;
    line-height: 1;
}
.guest-req-count {
    font-weight: 800;
    color: var(--gold);
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

/* ── Capacity guard: full-page notice + busy banner ───────────────────── */
/* Shown instead of the whole app when active_session_count() is over the
   hard limit — warm and party-themed, never "server error"-flavored. See
   streamlit_app._render_capacity_page(). */
.capacity-page {
    text-align: center;
    background: linear-gradient(135deg, rgba(var(--gold-rgb), 0.14) 0%, rgba(var(--violet-rgb), 0.1) 100%);
    border: 1px solid rgba(var(--gold-rgb), 0.35);
    border-radius: var(--radius-xl);
    padding: var(--space-8) var(--space-5);
    margin: var(--space-5) 0;
    box-shadow: var(--shadow-gold-lg);
}
.capacity-page-icon { font-size: 2.6rem; margin-bottom: var(--space-3); }
.capacity-page-title {
    font-size: 1.4rem;
    font-weight: 800;
    color: var(--gold-soft);
    margin-bottom: var(--space-3);
}
.capacity-page-message {
    color: var(--text-dim);
    font-size: 1rem;
    line-height: 1.6;
    max-width: 46ch;
    margin: 0 auto var(--space-4) auto;
}
.capacity-page-message strong { color: var(--text); }
.capacity-page-count {
    display: inline-block;
    margin-top: var(--space-2);
    color: var(--text-dimmer);
    font-size: 0.82rem;
}

/* Soft-limit banner: visitors are let through, just told it may be slow. */
.busy-banner {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    text-align: center;
    background: var(--warn-bg);
    border: 1px solid var(--warn-border);
    border-radius: var(--radius-md);
    padding: 10px var(--space-4);
    margin: 0 0 var(--space-4) 0;
    color: var(--text);
    font-size: 0.9rem;
    font-weight: 600;
}

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

/* ── Guest identity card (scanner: confirm before checking in) ─────────── */
.guest-identity-rows {
    margin-top: var(--space-3);
    border-top: 1px solid var(--border);
    padding-top: var(--space-3);
}
.guest-identity-row {
    display: flex;
    justify-content: space-between;
    gap: var(--space-4);
    padding: 5px 0;
    font-size: 0.95rem;
}
.guest-identity-label { color: var(--text-dim); flex: 0 0 auto; }
/* Long emails must wrap rather than push the value off a phone screen. */
.guest-identity-value {
    color: var(--text);
    font-weight: 600;
    text-align: right;
    word-break: break-word;
}
.guest-identity-value.is-strong { font-size: 1.05rem; color: var(--gold); }

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


_STAT_ACCENTS = {"gold", "ok", "warn", "err", "info", "violet", "cyan"}


def stat_tiles(items: list) -> str:
    """A responsive CSS-grid of stat tiles with per-tile visual hierarchy.

    `items` is a list of dicts, each describing one tile:
        {
            "label": str,             # required
            "value": Any,             # required — stringified + escaped
            "caption": str = "",      # optional secondary line
            "icon": str = "",         # optional emoji shown beside the label
            "accent": str = "",       # one of _STAT_ACCENTS, or "" for neutral
            "emphasis": str = "normal",  # "hero" for the number(s) that matter most
        }

    `accent` is purely a styling hook onto the existing design tokens
    (--ok/--warn/--err/--info/--gold/--violet/--cyan) — never a new raw
    color — and unrecognized values are dropped rather than interpolated, so
    a typo can't leak an arbitrary CSS class. A "hero" tile renders larger,
    with a tinted background, and spans two grid tracks so the operationally
    important numbers (e.g. Checked In vs Total Guests) visually lead the
    row instead of blending into a uniform grid of identical boxes; a hero
    tile with no explicit accent defaults to "gold" so it never looks flat.
    """
    tiles = []
    for item in items:
        label = item.get("label", "")
        value = item.get("value", "")
        caption = item.get("caption") or ""
        icon = item.get("icon") or ""
        emphasis = item.get("emphasis") or "normal"
        accent = item.get("accent") or ("gold" if emphasis == "hero" else "")
        if accent not in _STAT_ACCENTS:
            accent = ""

        classes = ["stat-tile"]
        if emphasis == "hero":
            classes.append("stat-tile-hero")
        if accent:
            classes.append(f"accent-{accent}")

        icon_html = f'<span class="stat-icon">{html.escape(icon)}</span>' if icon else ""
        cap_html = (
            f'<div class="stat-caption">{html.escape(str(caption))}</div>' if caption else ""
        )
        tiles.append(
            f'<div class="{" ".join(classes)}">'
            f'<div class="stat-label">{icon_html}<span>{html.escape(str(label))}</span></div>'
            f'<div class="stat-value">{html.escape(str(value))}</div>'
            f'{cap_html}'
            f'</div>'
        )
    return f'<div class="stat-grid">{"".join(tiles)}</div>'


def checkin_progress_meter(checked_in: int, total: int) -> str:
    """A labelled check-in progress meter, e.g. '6 of 13 checked in · 46%'.

    Replaces a bare st.progress() bar with a real progress element that
    states the counts in plain language rather than a lone percentage, and
    handles the zero-guests case (fresh install / just after a Danger Zone
    reset) without dividing by zero or drawing a meaningless empty bar.
    """
    checked_in = int(checked_in)
    total = int(total)

    if total <= 0:
        return (
            '<div class="progress-meter">'
            '<div class="progress-meter-track" role="progressbar" '
            'aria-valuenow="0" aria-valuemin="0" aria-valuemax="0" aria-label="Check-in progress">'
            '<div class="progress-meter-fill" style="width:0%;"></div></div>'
            '<div class="progress-meter-detail">No guests registered yet — the check-in rate '
            'will show up here once people sign up.</div>'
            '</div>'
        )

    pct = round(checked_in / total * 100, 1)
    pct_display = int(pct) if pct == int(pct) else pct
    pct_clamped = max(0.0, min(100.0, pct))
    return (
        '<div class="progress-meter">'
        f'<div class="progress-meter-track" role="progressbar" '
        f'aria-valuenow="{checked_in}" aria-valuemin="0" aria-valuemax="{total}" '
        f'aria-label="Check-in progress">'
        f'<div class="progress-meter-fill" style="width:{pct_clamped}%;"></div></div>'
        f'<div class="progress-meter-detail">{checked_in} of {total} checked in · {pct_display}%</div>'
        '</div>'
    )


# Below this many tickets left, the remaining-tickets meter switches to the
# warning accent — "8 left" should not look as calm as "180 left".
TICKETS_LOW_THRESHOLD = 25


def tickets_remaining(availability: dict, context: str = "") -> str:
    """A meter showing how many tickets are still available.

    `availability` is a utils.ticket_availability() payload. Returns an empty
    string when the cap is disabled (`unlimited`), so callers can render this
    unconditionally and get nothing when there is no cap to report.

    Colour follows scarcity: gold normally, warn under TICKETS_LOW_THRESHOLD,
    err at zero. `context` replaces the default note under the bar.
    """
    if not availability or availability.get("unlimited"):
        return ""

    cap = max(0, int(availability.get("cap", 0)))
    if cap <= 0:
        return ""
    remaining = max(0, int(availability.get("remaining", 0)))
    sold = max(0, min(cap, int(availability.get("sold", 0))))

    if remaining <= 0:
        state, note = "is-out", "Every ticket has been claimed."
    elif remaining <= TICKETS_LOW_THRESHOLD:
        state, note = "is-low", "Almost gone — register soon to be sure of your spot."
    else:
        state, note = "", "Tickets are first come, first served."
    if context:
        note = context

    plural = "s" if remaining != 1 else ""
    filled = round(sold / cap * 100, 1) if cap else 0.0
    return (
        f'<div class="tickets-left {state}">'
        '<div class="tickets-left-head">'
        f'<span class="tickets-left-count">🎟️ <strong>{remaining}</strong> ticket{plural} left</span>'
        f'<span class="tickets-left-of">{sold} of {cap} claimed</span>'
        '</div>'
        f'<div class="tickets-left-track" role="progressbar" aria-valuenow="{sold}" '
        f'aria-valuemin="0" aria-valuemax="{cap}" aria-label="Tickets claimed">'
        f'<div class="tickets-left-fill" style="width:{filled}%;"></div></div>'
        f'<div class="tickets-left-note">{html.escape(note)}</div>'
        '</div>'
    )


def sold_out_notice(message: str) -> str:
    """The notice shown in place of the Register form once the cap is hit.

    `message` is utils.SOLD_OUT_MESSAGE — kept in utils rather than inlined
    here so the same wording covers both this screen and the refusal a guest
    hits if the last ticket goes while their form is open.
    """
    return f"""
    <div class="sold-out-notice">
        <div class="sold-out-icon">🎟️</div>
        <div class="sold-out-title">Sold out — every ticket is claimed</div>
        <div class="sold-out-message">{html.escape(message)}</div>
    </div>
    """


def empty_state(icon: str, title: str, message: str) -> str:
    """A friendly placeholder for an otherwise-empty section.

    Used so a fresh install or a just-reset dashboard reads as "nothing here
    yet" rather than "something is broken".
    """
    return (
        '<div class="empty-state">'
        f'<div class="empty-state-icon">{html.escape(icon)}</div>'
        f'<div class="empty-state-title">{html.escape(title)}</div>'
        f'<div class="empty-state-message">{html.escape(message)}</div>'
        '</div>'
    )


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


def guest_names_requirement(ticket_count: int, provided: int = 0) -> str:
    """The live note telling the guest how many names their tickets need.

    `ticket_count` is the current value of the Register page's ticket
    selector (which lives outside the form, so changing it re-renders this);
    `provided` is how many names are currently saved for the booking, used
    only to show progress after a failed submit — a fresh form passes 0.

    One ticket per person means a booking of N tickets is the registrant plus
    N-1 named guests, which is exactly what utils.validate_registration
    enforces. Stating it here, in the same words and before the field, is the
    difference between a guest who fills it in correctly and one who submits
    and gets an error.
    """
    tickets = int(ticket_count)
    needed = max(tickets - 1, 0)

    if needed == 0:
        return (
            '<div class="guest-req is-solo">'
            '<span class="guest-req-icon">🎟️</span>'
            "<span>Just you on this booking — no other names needed. "
            "Bringing someone? Add a ticket for each person above.</span>"
            "</div>"
        )

    people_word = "guest" if needed == 1 else "guests"
    name_word = "name" if needed == 1 else "names"
    progress = f" You've entered {int(provided)} so far." if provided else ""
    return (
        '<div class="guest-req">'
        '<span class="guest-req-icon">👥</span>'
        f"<span>{tickets} tickets covers <strong>you plus "
        f'<span class="guest-req-count">{needed}</span> other {people_word}</strong> — '
        f"please enter their {name_word} below, one per line.{html.escape(progress)}</span>"
        "</div>"
    )


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


def capacity_full_page() -> str:
    """The friendly full-page "we're at capacity" screen (capacity guard).

    Shown instead of the whole app when too many sessions are active at
    once. Deliberately warm and party-themed, never server/error-flavored —
    the owner's ask was that anyone turned away should feel like the party
    is popular, not that something broke. Pair with an st.button("Retry")
    below this in the caller; HTML markup alone can't submit a rerun.

    Note this deliberately does NOT promise that a spot is being held. Tickets
    are capped (config.max_total_tickets()) and genuinely first come, first
    served, so a guest bounced off this screen must not be told to relax —
    only that nothing they've already completed is at risk.
    """
    return f"""
    <div class="capacity-page">
        <div class="capacity-page-icon">🎉</div>
        <div class="capacity-page-title">Whoa — lots of people checking this out right now!</div>
        <div class="capacity-page-message">
            So many guests are on the site at once that we're asking new visitors to hang back
            for just a moment so it stays fast for everyone.
            <br><br>
            <strong>Anything you've already done is safe</strong> — registrations and check-ins
            that went through are saved, and nothing is lost by waiting here.
            <br><br>
            Tickets are limited and go first come, first served, so try again in a moment —
            it'll be quick.
        </div>
    </div>
    """


def busy_banner() -> str:
    """A small, non-blocking banner shown when load is elevated but not yet
    at the hard capacity limit — the visitor gets through, just forewarned."""
    return (
        '<div class="busy-banner">'
        '🚦 Busier than usual right now — pages may take a little longer to load. Thanks for your patience!'
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


def guest_identity_card(guest: dict, bands: int, status_label: str, status: str = "found") -> str:
    """The "is this you?" card the Scanner shows before anyone is checked in.

    Door staff search by phone (guests often can't remember which email
    address their QR code went to), so the match has to be confirmed against
    a person, not just a number: every identifying field is listed —  name,
    email, phone — alongside what the booking is owed, tickets and the
    wristbands that go with them.

    `status` styles the card ("found" / "already" / "done") and
    `status_label` is the line staff read, e.g. "Not checked in yet".
    """
    status_map = {
        "found": "status-ok",
        "already": "status-warn",
        "done": "status-ok",
    }
    css_class = status_map.get(status, "status-ok")

    try:
        tickets = int(guest.get("ticket_count") or 1)
    except (TypeError, ValueError):
        tickets = 1

    rows = [
        ("Email", guest.get("email") or "—", False),
        ("Phone", guest.get("phone") or "— (registered before phone was required)", False),
        ("Tickets", str(tickets), True),
        ("Wristbands", str(bands), True),
    ]

    # Names are collected at registration, one per ticket beyond the booker
    # (see utils.additional_guests_expected), so door staff can read the
    # whole party off this card. Bookings made before names were required
    # can still be short — say so plainly rather than silently listing
    # fewer people than are standing there.
    extra_names = [n for n in (guest.get("plus_one_name") or "").split("\n") if n.strip()]
    expected = max(tickets - 1, 0)
    if extra_names or expected:
        label = f"Additional guests ({len(extra_names)} of {expected})"
        value = ", ".join(extra_names) if extra_names else "— none on file"
        rows.append((label, value, False))

    # Concatenated for the same reason as guest_result_card() above: a blank
    # line inside the HTML block would end it and dump the rest as text.
    parts = [f'<div class="guest-result-card {css_class}">']
    parts.append(f'<div class="guest-result-name">{html.escape(str(guest.get("name") or "Unknown"))}</div>')
    parts.append(f'<div class="guest-result-status">{html.escape(status_label)}</div>')
    parts.append('<div class="guest-identity-rows">')
    for label, value, strong in rows:
        strong_class = " is-strong" if strong else ""
        parts.append(
            '<div class="guest-identity-row">'
            f'<span class="guest-identity-label">{html.escape(label)}</span>'
            f'<span class="guest-identity-value{strong_class}">{html.escape(str(value))}</span>'
            "</div>"
        )
    parts.append("</div></div>")
    return "".join(parts)
