"""Token-driven styling for the Streamlit GIS workbench shell."""

from typing import Final

import streamlit as st

WORKBENCH_CSS: Final = """
<style>
:root {
  --shell-canvas: #f4f4f4;
  --shell-surface: #ffffff;
  --shell-layer: #e8e8e8;
  --shell-hover: #e0e0e0;
  --chrome-navy: #0b1f33;
  --chrome-navy-hover: #142f4c;
  --text-primary: #161616;
  --text-secondary: #525252;
  --text-muted: #6f6f6f;
  --text-inverse: #ffffff;
  --border-subtle: #c6c6c6;
  --border-strong: #8d8d8d;
  --accent-blue: #0f62fe;
  --accent-blue-hover: #0353e9;
  --accent-blue-active: #002d9c;
  --status-success: #198038;
  --status-error: #da1e28;
  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-5: 20px;
  --space-6: 24px;
  --space-8: 32px;
  --radius-0: 0;
  --radius-1: 2px;
  --radius-2: 4px;
  --project-bar-height: 48px;
  --control-height: 40px;
  --type-product: 1rem;
  --type-panel: .75rem;
  --type-body: .875rem;
  --type-data: .875rem;
  --type-caption: .75rem;
}
html, body, [class*="css"] {
  color: var(--text-primary);
  font-family: "IBM Plex Sans", "Noto Sans SC", "Microsoft YaHei", sans-serif;
  letter-spacing: 0;
}
[data-testid="stAppViewContainer"] { background: var(--shell-canvas); }
[data-testid="stHeader"] { background: var(--chrome-navy); }
[data-testid="stMainBlockContainer"] {
  max-width: none;
  padding: var(--space-4);
  padding-top: var(--space-3);
}
[data-testid="stVerticalBlock"], [data-testid="stColumn"], [data-testid="column"] { min-width: 0; }
[data-testid="stHorizontalBlock"] { gap: var(--space-4); }
p, label, [data-testid="stCaptionContainer"] {
  font-size: var(--type-body) !important;
  line-height: 1.45;
}
.project-bar {
  align-items: center;
  background: var(--chrome-navy);
  border-bottom: var(--space-1) solid var(--accent-blue);
  box-sizing: border-box;
  color: var(--text-inverse);
  display: grid;
  gap: var(--space-4);
  grid-template-columns: minmax(12rem, 1fr) auto minmax(16rem, 1.4fr);
  min-height: var(--project-bar-height);
  padding: var(--space-2) var(--space-4);
}
.route-back-space { height: var(--space-8); }
[data-testid="stButton"]:has(button[key="back-selector"]) { position: relative; z-index: 20; }
.project-identity { font-size: var(--type-product); font-weight: 600; }
.project-identity span { color: var(--border-subtle); font-weight: 400; }
.stage-rail { display: flex; flex-wrap: wrap; gap: var(--space-4); }
.stage-rail span {
  color: var(--border-subtle);
  font-size: var(--type-panel);
  font-weight: 600;
  white-space: nowrap;
}
.stage-rail span:first-child, .project-status strong { color: var(--text-inverse); }
.project-status {
  font-size: var(--type-caption);
  min-width: 0;
  overflow-wrap: anywhere;
  text-align: right;
}
.selector-bar { margin-bottom: var(--space-8); }
.selector-options { margin: 0 auto; max-width: 64rem; }
.selector-options [data-testid="stHorizontalBlock"] { justify-content: center; }
.selector-heading { margin: var(--space-8) auto; max-width: 54rem; text-align: center; }
.selector-heading h1 { font-size: clamp(2rem, 5vw, 4rem); line-height: 1.05; margin: var(--space-3) 0; }
.selector-heading p { color: var(--text-secondary); margin: 0; }
.selector-heading .panel-index { display: block; letter-spacing: .12em; }
.selector-hint { display: flex; justify-content: space-around; margin: var(--space-3) auto 0; max-width: 52rem; }
.selector-hint span { color: var(--text-muted); font-size: var(--type-caption); }
.library-header, .library-row { border-bottom: 1px solid var(--border-subtle); }
.library-header { color: var(--text-muted); display: grid; grid-template-columns: 8fr 2fr 2fr; font-size: var(--type-caption); padding: var(--space-2) 0; }
.library-row { padding: var(--space-2) 0; }
.library-row [data-testid="stHorizontalBlock"] { align-items: center; margin: 0; }
.library-row [data-testid="stButton"] { display: inline-block; width: auto; }
.library-row [data-testid="stButton"] button[aria-label="删除"] { background: #da1e28; border-color: #da1e28; color: #fff; }
.library-row [data-testid="stButton"] button[aria-label="删除"]:hover { background: #b81921; border-color: #b81921; }
div[data-testid="stButton"]:has(button[key="open-view"]) button,
div[data-testid="stButton"]:has(button[key="open-delivery"]) button,
div[data-testid="stButton"]:has(button[key="open-management"]) button {
  aspect-ratio: 1;
  border-radius: 50% !important;
  font-size: clamp(1rem, 2vw, 1.35rem);
  margin: 0 auto;
  max-width: 20rem;
  min-height: 12rem;
  width: min(100%, 20rem);
}
.status-dot {
  background: var(--status-success);
  display: inline-block;
  height: var(--space-2);
  margin-right: var(--space-2);
  width: var(--space-2);
}
.workbench-panel-header {
  align-items: baseline;
  border-bottom: 1px solid var(--border-subtle);
  display: flex;
  gap: var(--space-2);
  margin: var(--space-3) 0 var(--space-3);
  min-height: var(--space-8);
  padding-bottom: var(--space-2);
}
.panel-index {
  color: var(--accent-blue);
  font-family: "IBM Plex Mono", "SFMono-Regular", Consolas, monospace;
  font-size: var(--type-panel);
  font-weight: 600;
}
.panel-title { font-size: var(--type-panel); font-weight: 600; }
.panel-state { color: var(--text-muted); font-size: var(--type-caption); margin-left: auto; }
.inspection-list { border-top: 1px solid var(--border-subtle); }
.inspection-row {
  align-items: baseline;
  border-bottom: 1px solid var(--border-subtle);
  display: flex;
  gap: var(--space-3);
  justify-content: space-between;
  min-height: var(--control-height);
  padding: var(--space-2) 0;
}
.inspection-row span { color: var(--text-secondary); font-size: var(--type-caption); }
.inspection-row strong {
  font-family: "IBM Plex Mono", "SFMono-Regular", Consolas, monospace;
  font-size: var(--type-data);
  font-variant-numeric: tabular-nums;
  font-weight: 500;
}
.delivery-note { color: var(--text-secondary); font-size: var(--type-caption); margin-bottom: var(--space-3); }
[data-testid="stFileUploader"], .stAlert, [data-testid="stDataFrame"] { border-radius: var(--radius-0) !important; }
.stButton > button, [data-testid="stDownloadButton"] > button {
  border-color: var(--border-strong);
  border-radius: var(--radius-1) !important;
  min-height: var(--control-height);
  transition: background-color 100ms, transform 100ms;
  width: 100%;
}
.stButton > button[kind="primary"] {
  background: var(--accent-blue);
  border-color: var(--accent-blue);
  color: var(--text-inverse);
}
.stButton > button[kind="primary"]:hover { background: var(--accent-blue-hover); }
.stButton > button:active, [data-testid="stDownloadButton"] > button:active { transform: translateY(1px); }
button:focus-visible, input:focus-visible {
  outline: 2px solid var(--accent-blue) !important;
  outline-offset: 2px;
}
iframe[data-testid="stCustomComponentV1"] {
  border: 1px solid var(--border-strong) !important;
  border-radius: var(--radius-0) !important;
  max-width: 100%;
  width: 100% !important;
}
pre, code, [data-testid="stDataFrame"] { max-width: 100%; overflow: auto; }
@media (max-width: 1023px) {
  [data-testid="stHorizontalBlock"] { flex-direction: column; gap: var(--space-2); }
  [data-testid="stColumn"], [data-testid="column"] {
    width: 100% !important;
    max-width: 100% !important;
    flex: 1 1 100% !important;
  }
  .project-bar { grid-template-columns: 1fr 1fr; }
  .stage-rail { grid-column: 1 / -1; grid-row: 2; }
  iframe[data-testid="stCustomComponentV1"] { height: 560px !important; }
}
@media (max-width: 767px) {
  [data-testid="stMainBlockContainer"] { padding: var(--space-3); }
  .project-bar { display: flex; align-items: flex-start; flex-direction: column; gap: var(--space-2); }
  .project-status { text-align: left; }
  iframe[data-testid="stCustomComponentV1"] { height: 500px !important; }
  .selector-heading { margin: var(--space-6) auto; }
  .selector-hint { display: none; }
  .route-back-space { height: var(--space-6); }
}
@media (prefers-reduced-motion: reduce) {
  * { animation: none !important; transition: none !important; transform: none !important; }
}
</style>
"""


def render_styles() -> None:
    """Apply the DESIGN.md token contract to native Streamlit elements."""
    st.markdown(WORKBENCH_CSS, unsafe_allow_html=True)
