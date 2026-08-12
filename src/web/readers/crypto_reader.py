from crypto_tracker.snapshot import CryptoSnapshot, load_last_snapshot


def read_crypto_snapshot() -> CryptoSnapshot | None:
    """Read the local crypto snapshot without making an API request."""
    return load_last_snapshot()
