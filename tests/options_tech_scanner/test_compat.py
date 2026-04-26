from options_tech_scanner.backtest_v3 import infer_signal_side
from options_tech_scanner.scan import scan_universe


def test_legacy_backtest_shim_reexports_current_api():
    assert infer_signal_side("bullish_aligned") == "bullish"


def test_legacy_scan_shim_reexports_current_api():
    assert callable(scan_universe)
