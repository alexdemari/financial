from __future__ import annotations

import argparse
import json
import logging
import os
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from crypto_tracker.binance_client import BinanceAPIError, BinanceReadOnlyClient
from irpf_report.ptax import CACHE_DIR, get_ptax, load_latest_cached_ptax

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT_PATH = PROJECT_ROOT / "data/crypto/snapshot.json"
STALE_AFTER = timedelta(hours=4)
logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class CryptoPosition:
    asset: str
    quantity: float
    price_usdt: float
    value_usdt: float
    value_brl: float


@dataclass(frozen=True, slots=True)
class CryptoSnapshot:
    positions: list[CryptoPosition]
    total_usdt: float
    total_brl: float
    ptax_used: float
    fetched_at: str

    @property
    def stale(self) -> bool:
        try:
            fetched_at = datetime.fromisoformat(self.fetched_at)
            if fetched_at.tzinfo is None:
                fetched_at = fetched_at.replace(tzinfo=UTC)
        except ValueError:
            return True
        return datetime.now(UTC) - fetched_at > STALE_AFTER


def fetch_and_save(ptax: float) -> CryptoSnapshot:
    """Fetch Binance Spot balances and persist a BRL-valued snapshot."""
    api_key = os.getenv("BINANCE_API_KEY", "").strip()
    api_secret = os.getenv("BINANCE_API_SECRET", "").strip()
    if not api_key or not api_secret:
        logger.warning("BINANCE_API_KEY and BINANCE_API_SECRET are not configured")
        snapshot = _empty_snapshot(ptax)
        _save_snapshot(snapshot)
        return snapshot

    try:
        client = BinanceReadOnlyClient(api_key, api_secret)
        balances = client.get_spot_balances()
        assets = [str(balance["asset"]) for balance in balances]
        symbols = [f"{asset}USDT" for asset in assets if asset != "USDT"]
        prices = client.get_prices(symbols)
    except BinanceAPIError:
        logger.exception("Unable to fetch Binance snapshot")
        raise

    positions = []
    for balance in balances:
        asset = str(balance["asset"])
        quantity = float(balance.get("free", 0.0)) + float(balance.get("locked", 0.0))
        price_usdt = 1.0 if asset == "USDT" else prices.get(f"{asset}USDT", 0.0)
        value_usdt = quantity * price_usdt
        if value_usdt < 1.0:
            continue
        positions.append(
            CryptoPosition(
                asset=asset,
                quantity=quantity,
                price_usdt=price_usdt,
                value_usdt=value_usdt,
                value_brl=value_usdt * ptax,
            )
        )

    snapshot = CryptoSnapshot(
        positions=positions,
        total_usdt=sum(position.value_usdt for position in positions),
        total_brl=sum(position.value_brl for position in positions),
        ptax_used=ptax,
        fetched_at=datetime.now(UTC).isoformat(),
    )
    _save_snapshot(snapshot)
    return snapshot


def load_last_snapshot() -> CryptoSnapshot | None:
    """Load the latest local snapshot, returning None for missing/invalid data."""
    if not SNAPSHOT_PATH.exists():
        return None
    try:
        raw_snapshot = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
        positions = [
            CryptoPosition(**position) for position in raw_snapshot["positions"]
        ]
        return CryptoSnapshot(
            positions=positions,
            total_usdt=float(raw_snapshot["total_usdt"]),
            total_brl=float(raw_snapshot["total_brl"]),
            ptax_used=float(raw_snapshot["ptax_used"]),
            fetched_at=str(raw_snapshot["fetched_at"]),
        )
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        logger.warning("Ignoring invalid crypto snapshot at %s", SNAPSHOT_PATH)
        return None


def _save_snapshot(snapshot: CryptoSnapshot) -> None:
    SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOT_PATH.write_text(
        json.dumps(asdict(snapshot), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _empty_snapshot(ptax: float) -> CryptoSnapshot:
    return CryptoSnapshot([], 0.0, 0.0, ptax, datetime.now(UTC).isoformat())


def _resolve_ptax() -> float:
    cache_dir = PROJECT_ROOT / CACHE_DIR
    cached = load_latest_cached_ptax(cache_dir)
    if cached is not None:
        return cached[0]
    rate = get_ptax(date.today(), cache_dir=cache_dir)
    if rate is None:
        raise RuntimeError("PTAX indisponível; informe --ptax manualmente")
    return rate


def main() -> None:
    parser = argparse.ArgumentParser(description="Save a Binance Spot snapshot")
    parser.add_argument("--ptax", type=float, help="USD/BRL rate for conversion")
    arguments = parser.parse_args()
    if arguments.ptax is not None:
        ptax = arguments.ptax
    elif (
        os.getenv("BINANCE_API_KEY", "").strip()
        and os.getenv("BINANCE_API_SECRET", "").strip()
    ):
        ptax = _resolve_ptax()
    else:
        ptax = 0.0
    snapshot = fetch_and_save(ptax)
    print(
        f"Snapshot salvo: {len(snapshot.positions)} posições, BRL {snapshot.total_brl:,.2f}"
    )


if __name__ == "__main__":
    main()
