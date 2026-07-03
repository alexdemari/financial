from __future__ import annotations

from pathlib import Path

KNOWN_ALIASES = {
    "opcoes": "BTG-Opções",
    "opções": "BTG-Opções",
    "geral": "BTG-Geral",
}


class UnknownAccountError(ValueError):
    """Raised when a filename doesn't match a known BTG account alias."""


def detect_account(filepath: Path) -> str:
    """Detect account alias from filename keywords.

    Raises UnknownAccountError if no keyword matches — writer/merger only
    know how to route BTG-Opções and BTG-Geral, so a file that can't be
    classified must not proceed to produce output the dashboard never reads.
    """
    stem = filepath.stem.lower()
    for keyword, alias in KNOWN_ALIASES.items():
        if keyword in stem:
            return alias
    raise UnknownAccountError(
        f"Cannot detect account for '{filepath.name}'. "
        f"Rename to include '_opcoes' or '_geral' in the filename."
    )
