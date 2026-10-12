"""Read-only reconciliation between a B3 custody snapshot and BTG positions."""

from __future__ import annotations

import argparse
import csv
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ReconciliationRow:
    institution: str
    product: str
    b3_quantity: float
    btg_quantity: float

    @property
    def status(self) -> str:
        if not self.b3_quantity:
            return "excess_btg"
        if not self.btg_quantity:
            return "missing_btg"
        if abs(self.b3_quantity - self.btg_quantity) > 1e-9:
            return "quantity_mismatch"
        return "in_sync"


def reconcile(snapshot: Path, btg_paths: list[Path]) -> list[ReconciliationRow]:
    """Compare normalized B3 and BTG quantities without changing either source."""
    b3 = _aggregate_b3(snapshot)
    btg = _aggregate_btg(btg_paths)
    return [
        ReconciliationRow(institution, product, b3.get(key, 0.0), btg.get(key, 0.0))
        for key in sorted(set(b3) | set(btg))
        for institution, product in [key]
    ]


def write_report(rows: list[ReconciliationRow], output_dir: Path) -> Path:
    """Write an auditable local report and return its path."""
    output_dir.mkdir(parents=True, exist_ok=True)
    report = output_dir / "b3_reconciliation_latest.md"
    counts = {
        status: sum(row.status == status for row in rows)
        for status in ("in_sync", "missing_btg", "excess_btg", "quantity_mismatch")
    }
    lines = [
        "# B3 × BTG reconciliation",
        "",
        "Read-only audit. No source positions, cash, or totals were modified.",
        "",
        "| Status | Count |",
        "| --- | ---: |",
        *[f"| {status} | {count} |" for status, count in counts.items()],
        "",
        "| Institution | Product | B3 quantity | BTG quantity | Status |",
        "| --- | --- | ---: | ---: | --- |",
        *[
            f"| {row.institution} | {row.product} | {row.b3_quantity:g} | {row.btg_quantity:g} | {row.status} |"
            for row in rows
            if row.status != "in_sync"
        ],
    ]
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def _aggregate_b3(path: Path) -> dict[tuple[str, str], float]:
    totals: defaultdict[tuple[str, str], float] = defaultdict(float)
    with path.open(encoding="utf-8", newline="") as input_file:
        for row in csv.DictReader(input_file):
            if row["asset_class"] not in {"acoes_br", "bdr"}:
                continue
            product = row.get("trading_code") or row["product"]
            totals[
                (_normalize_institution(row["institution"]), _normalize(product))
            ] += float(row["quantity"])
    return dict(totals)


def _aggregate_btg(paths: list[Path]) -> dict[tuple[str, str], float]:
    totals: defaultdict[tuple[str, str], float] = defaultdict(float)
    for path in paths:
        if not path.exists():
            continue
        with path.open(encoding="utf-8", newline="") as input_file:
            for row in csv.DictReader(input_file):
                if row.get("asset_type", "").upper() not in {"ACAO", "AÇÃO", "BDR"}:
                    continue
                totals[("BTG", _normalize(row.get("codigo", "")))] += float(
                    row.get("quantidade") or 0
                )
    return dict(totals)


def _normalize_institution(value: str) -> str:
    normalized = _normalize(value)
    return "BTG" if "BTG" in normalized else normalized


def _normalize(value: str) -> str:
    text = (
        unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    )
    return re.sub(r"[^A-Z0-9]", "", text.upper())


def main() -> None:
    """Generate a reconciliation report while keeping financial details off stdout."""
    parser = argparse.ArgumentParser(
        description="Reconcile B3 custody snapshot against BTG positions"
    )
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument(
        "--btg-opcoes", type=Path, default=Path("data/btg/btg_opcoes_positions.csv")
    )
    parser.add_argument(
        "--btg-geral", type=Path, default=Path("data/btg/btg_geral_positions.csv")
    )
    parser.add_argument("--output-dir", type=Path, default=Path("reports"))
    arguments = parser.parse_args()
    report = write_report(
        reconcile(arguments.snapshot, [arguments.btg_opcoes, arguments.btg_geral]),
        arguments.output_dir,
    )
    print(f"B3 reconciliation report saved: {report}")


if __name__ == "__main__":
    main()
