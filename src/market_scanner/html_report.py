from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

import markdown as _md

_DARK_CSS = """
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Helvetica Neue', sans-serif;
    background: #0f1117;
    color: #e2e8f0;
    font-size: 14px;
    line-height: 1.6;
}

.container { max-width: 1100px; margin: 0 auto; padding: 28px 20px 60px; }

h1 { font-size: 22px; font-weight: 700; color: #f1f5f9; margin: 28px 0 6px; border: none; }
h2 {
    font-size: 16px; font-weight: 600; color: #cbd5e1;
    margin: 28px 0 10px;
    padding-bottom: 6px;
    border-bottom: 1px solid #2d3139;
}
h3 { font-size: 14px; font-weight: 600; color: #94a3b8; margin: 20px 0 8px; }

p { margin: 8px 0; color: #cbd5e1; }

hr {
    border: none;
    border-top: 1px solid #2d3139;
    margin: 24px 0;
}

strong { color: #f1f5f9; font-weight: 600; }
em { color: #94a3b8; }

/* tables */
table {
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
    margin: 12px 0 20px;
    background: #151820;
    border-radius: 6px;
    overflow: hidden;
}
thead th {
    background: #1e2230;
    color: #8b95a1;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: .05em;
    padding: 9px 12px;
    text-align: left;
    border-bottom: 1px solid #2d3139;
    white-space: nowrap;
}
td {
    padding: 8px 12px;
    border-bottom: 1px solid #1e2230;
    color: #cbd5e1;
    vertical-align: top;
}
tr:last-child td { border-bottom: none; }
tr:hover td { background: #1a1d26; }

/* action bucket colours */
td:has-text("candidate") { color: #34d399; }

/* inline code */
code {
    background: #1e2230;
    color: #a5b4fc;
    padding: 1px 5px;
    border-radius: 3px;
    font-size: 12px;
    font-family: 'Fira Code', 'Cascadia Code', monospace;
}

pre {
    background: #1e2230;
    border: 1px solid #2d3139;
    border-radius: 6px;
    padding: 14px 16px;
    overflow-x: auto;
    margin: 12px 0;
}
pre code { background: none; padding: 0; color: #a5b4fc; }

ul, ol { padding-left: 20px; margin: 8px 0; }
li { color: #cbd5e1; margin: 3px 0; }

/* coloured signal words via text patterns */
.pos, td[class~=pos] { color: #34d399 !important; }
.neg, td[class~=neg] { color: #f87171 !important; }

/* footer */
.footer {
    text-align: center;
    color: #4b5563;
    font-size: 11px;
    margin-top: 40px;
    padding-top: 16px;
    border-top: 1px solid #1e2230;
}
"""

_COLOUR_RULES: list[tuple[re.Pattern[str], str]] = [
    # action_bucket cells
    (re.compile(r"\bcandidate\b"), "#34d399"),
    (re.compile(r"\bwatchlist\b"), "#60a5fa"),
    (re.compile(r"\bavoid\b"), "#f87171"),
    (re.compile(r"\bneeds_review\b"), "#fbbf24"),
    # alignment
    (re.compile(r"\bbullish_aligned\b"), "#34d399"),
    (re.compile(r"\bbearish_aligned\b"), "#f87171"),
    # EXIT / WATCH / HOLD from exit_monitor
    (re.compile(r"\bEXIT\b"), "#f87171"),
    (re.compile(r"\bWATCH\b"), "#fbbf24"),
    (re.compile(r"\bHOLD\b"), "#34d399"),
    # BUY / OVERPRICED from dividend tracker
    (re.compile(r"\bBUY\b"), "#34d399"),
    (re.compile(r"\bOVERPRICED\b"), "#f87171"),
]


def _colourise_td(html: str) -> str:
    """Apply colour spans inside <td> cells for known signal words."""

    def _replace_in_td(m: re.Match[str]) -> str:
        cell = m.group(0)
        for pattern, colour in _COLOUR_RULES:
            cell = pattern.sub(
                lambda mo,
                c=colour: f"<span style='color:{c};font-weight:600'>{mo.group()}</span>",
                cell,
            )
        return cell

    return re.sub(r"<td[^>]*>.*?</td>", _replace_in_td, html, flags=re.DOTALL)


def render_daily_html(md_content: str, title: str = "Daily Market Report") -> str:
    body_html = _md.markdown(
        md_content,
        extensions=["tables", "fenced_code", "nl2br"],
    )
    body_html = _colourise_td(body_html)
    generated = datetime.now().strftime("%Y-%m-%d %H:%M")
    return (
        "<!DOCTYPE html>\n"
        "<html lang='en'>\n"
        "<head>\n"
        "<meta charset='UTF-8'>\n"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>\n"
        f"<title>{title}</title>\n"
        f"<style>{_DARK_CSS}</style>\n"
        "</head>\n"
        "<body>\n"
        "<div class='container'>\n"
        f"{body_html}\n"
        f"<div class='footer'>Generated {generated}</div>\n"
        "</div>\n"
        "</body></html>"
    )


def write_daily_html(
    md_content: str,
    output_path: str | Path,
    title: str = "Daily Market Report",
) -> Path:
    html_path = Path(str(output_path).replace(".md", ".html"))
    html_path.write_text(render_daily_html(md_content, title=title), encoding="utf-8")
    return html_path
