import os

import pandas as pd

from market_scanner.cache import CachedAnalyzer, get_or_compute_historical


def _make_df() -> pd.DataFrame:
    return pd.DataFrame({"value": [1, 2, 3]})


class CountingAnalyzer:
    def __init__(self):
        self.calls = 0
        self._result = _make_df()

    def generate_historical_signals(self, symbol, df):
        self.calls += 1
        return self._result

    def generate_signal(self, symbol, df):
        return {"signal": "bullish"}


def _write_fake_csv(path):
    path.write_text("date,close\n2024-01-01,100\n")


def test_cache_miss_computes_and_writes(tmp_path):
    csv_path = tmp_path / "AAPL.csv"
    _write_fake_csv(csv_path)
    cache_dir = tmp_path / "cache"
    analyzer = CountingAnalyzer()
    df = _make_df()

    result = get_or_compute_historical(
        analyzer=analyzer,
        symbol="AAPL",
        df=df,
        csv_path=csv_path,
        cache_dir=cache_dir,
        model_name="lux",
    )

    assert analyzer.calls == 1
    pd.testing.assert_frame_equal(result, analyzer._result)

    # Check that a .pkl file was written under cache_dir/lux/
    pkl_files = list((cache_dir / "lux").glob("*.pkl"))
    assert len(pkl_files) == 1


def test_cache_hit_skips_computation(tmp_path):
    csv_path = tmp_path / "AAPL.csv"
    _write_fake_csv(csv_path)
    cache_dir = tmp_path / "cache"
    analyzer = CountingAnalyzer()
    df = _make_df()

    # First call — computes and caches
    get_or_compute_historical(
        analyzer=analyzer,
        symbol="AAPL",
        df=df,
        csv_path=csv_path,
        cache_dir=cache_dir,
        model_name="lux",
    )
    assert analyzer.calls == 1

    # Second call — should hit cache, not call analyzer again
    result = get_or_compute_historical(
        analyzer=analyzer,
        symbol="AAPL",
        df=df,
        csv_path=csv_path,
        cache_dir=cache_dir,
        model_name="lux",
    )
    assert analyzer.calls == 1
    pd.testing.assert_frame_equal(result, analyzer._result)


def test_cache_invalidated_on_mtime_change(tmp_path):
    csv_path = tmp_path / "AAPL.csv"
    _write_fake_csv(csv_path)
    cache_dir = tmp_path / "cache"
    analyzer = CountingAnalyzer()
    df = _make_df()

    # First call — computes and caches
    get_or_compute_historical(
        analyzer=analyzer,
        symbol="AAPL",
        df=df,
        csv_path=csv_path,
        cache_dir=cache_dir,
        model_name="lux",
    )
    assert analyzer.calls == 1

    # Touch the file to change its mtime
    new_mtime = csv_path.stat().st_mtime + 2.0
    os.utime(csv_path, (new_mtime, new_mtime))

    # Second call — mtime changed, cache key is different, must recompute
    get_or_compute_historical(
        analyzer=analyzer,
        symbol="AAPL",
        df=df,
        csv_path=csv_path,
        cache_dir=cache_dir,
        model_name="lux",
    )
    assert analyzer.calls == 2


def test_corrupt_cache_falls_back_silently(tmp_path):
    csv_path = tmp_path / "AAPL.csv"
    _write_fake_csv(csv_path)
    cache_dir = tmp_path / "cache"
    analyzer = CountingAnalyzer()
    df = _make_df()

    # Pre-populate with garbage bytes at the expected cache path
    from market_scanner.cache import _cache_key

    key = _cache_key("AAPL", csv_path)
    pkl_dir = cache_dir / "lux"
    pkl_dir.mkdir(parents=True, exist_ok=True)
    corrupt_path = pkl_dir / f"{key}.pkl"
    corrupt_path.write_bytes(b"not-a-pickle")

    # Should not raise — silently falls back to computing
    result = get_or_compute_historical(
        analyzer=analyzer,
        symbol="AAPL",
        df=df,
        csv_path=csv_path,
        cache_dir=cache_dir,
        model_name="lux",
    )

    assert analyzer.calls == 1
    pd.testing.assert_frame_equal(result, analyzer._result)


def test_cache_disabled_when_cache_dir_none(tmp_path):
    csv_path = tmp_path / "AAPL.csv"
    _write_fake_csv(csv_path)
    analyzer = CountingAnalyzer()
    df = _make_df()

    result = get_or_compute_historical(
        analyzer=analyzer,
        symbol="AAPL",
        df=df,
        csv_path=csv_path,
        cache_dir=None,
        model_name="lux",
    )

    assert analyzer.calls == 1
    pd.testing.assert_frame_equal(result, analyzer._result)
    # No pkl files should exist anywhere
    assert not list(tmp_path.rglob("*.pkl"))


def test_cache_disabled_when_csv_path_none(tmp_path):
    cache_dir = tmp_path / "cache"
    analyzer = CountingAnalyzer()
    df = _make_df()

    result = get_or_compute_historical(
        analyzer=analyzer,
        symbol="AAPL",
        df=df,
        csv_path=None,
        cache_dir=cache_dir,
        model_name="lux",
    )

    assert analyzer.calls == 1
    pd.testing.assert_frame_equal(result, analyzer._result)
    # cache_dir should not have been created
    assert not cache_dir.exists()


def test_cached_analyzer_wraps_both_methods(tmp_path):
    csv_path = tmp_path / "AAPL.csv"
    _write_fake_csv(csv_path)
    cache_dir = tmp_path / "cache"
    inner = CountingAnalyzer()
    df = _make_df()

    cached = CachedAnalyzer(
        inner,
        csv_path=csv_path,
        cache_dir=cache_dir,
        model_name="smc",
    )

    # generate_signal delegates directly to the inner analyzer
    sig = cached.generate_signal("AAPL", df)
    assert sig == {"signal": "bullish"}

    # First generate_historical_signals — miss, calls inner
    result1 = cached.generate_historical_signals("AAPL", df)
    assert inner.calls == 1

    # Second call — hit, inner is NOT called again
    result2 = cached.generate_historical_signals("AAPL", df)
    assert inner.calls == 1
    pd.testing.assert_frame_equal(result1, result2)
