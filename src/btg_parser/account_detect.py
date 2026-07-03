from __future__ import annotations

from pathlib import Path

KNOWN_ALIASES = {
    "opcoes": "BTG-Opções",
    "opções": "BTG-Opções",
    "geral": "BTG-Geral",
}


def detect_account(filepath: Path) -> str:
    """Detect account alias from filename keywords, defaulting to BTG-Unknown."""
    stem = filepath.stem.lower()
    for keyword, alias in KNOWN_ALIASES.items():
        if keyword in stem:
            return alias
    print(
        f"⚠ Cannot detect account for '{filepath.name}'.\n"
        f"  Rename to include '_opcoes' or '_geral' in the filename.\n"
        f"  Defaulting to 'BTG-Unknown'."
    )
    return "BTG-Unknown"
