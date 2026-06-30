from __future__ import annotations

from pathlib import Path

import markdown

from web.readers.common import file_mtime


def render_markdown(path: Path) -> dict:
    if not path.exists():
        return {"html": "", "last_updated": None, "exists": False}
    text = path.read_text(encoding="utf-8")
    return {
        "html": markdown.markdown(text, extensions=["tables", "fenced_code"]),
        "last_updated": file_mtime(path),
        "exists": True,
    }
