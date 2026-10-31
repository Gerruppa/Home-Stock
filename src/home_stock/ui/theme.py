"""The look of the window: a light theme with one colour per kind of urgency (expired, expiring, to buy)."""

from nicegui import ui

# Pantry-label colours; the status colours are also the ones the Start sections and Product badges use
INK = "#1f2a24"
PAPER = "#f2f4ef"
GREEN = "#2f6b4f"
EXPIRED = "#b3261e"
EXPIRING = "#a85d00"
TO_BUY = "#2d5f7a"

# Width of the content column of every tab
CONTENT_WIDTH = "46rem"

_CSS = f"""
body {{ background: {PAPER}; color: {INK}; }}
.q-header {{ background: {GREEN}; }}
.q-tabs {{ background: white; border-bottom: 1px solid #d9ded6; }}
.q-tab {{ color: #4b5a51; }}
.q-tab--active {{ color: {GREEN}; }}
.q-tab__label {{ font-weight: 500; letter-spacing: 0; text-transform: none; font-size: 0.95rem; }}
.q-tab-panels, .q-tab-panel {{ background: transparent; }}
.hs-page {{ width: 100%; max-width: {CONTENT_WIDTH}; margin: 0 auto; padding: 1.5rem 1rem 5rem; }}
.hs-section {{ background: white; border: 1px solid #d9ded6; border-left: 6px solid var(--hs-accent);
    border-radius: 6px; padding: 0.9rem 1.1rem 1rem; }}
.hs-section + .hs-section {{ margin-top: 1rem; }}
.hs-section-title {{ color: var(--hs-accent); font-size: 1.15rem; font-weight: 600; }}
.hs-expired {{ --hs-accent: {EXPIRED}; }}
.hs-expiring {{ --hs-accent: {EXPIRING}; }}
.hs-running-low {{ --hs-accent: {TO_BUY}; }}
.hs-category {{ --hs-accent: {GREEN}; }}
.hs-qty {{ font-weight: 500; font-variant-numeric: tabular-nums; white-space: nowrap; }}
.hs-qty-low {{ color: {TO_BUY}; }}
.hs-line {{ font-size: 1rem; line-height: 1.5; padding: 0.3rem 0; border-top: 1px solid #e8ece5; }}
.hs-line:first-of-type {{ border-top: 0; }}
.hs-empty {{ color: #6b7a70; }}
"""


def apply_theme() -> None:
    """Light only (the system's dark mode would paint the page black behind the white cards), green as the brand."""
    ui.dark_mode(False)
    ui.colors(primary=GREEN, secondary=TO_BUY, accent=EXPIRING, negative=EXPIRED, warning=EXPIRING)
    ui.add_css(_CSS)
