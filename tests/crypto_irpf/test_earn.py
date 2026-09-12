from crypto_irpf.earn import summarize_earn
from crypto_trades.models import EarnRecord


def test_earn_is_summarized_by_type():
    records = [
        EarnRecord(
            str(index),
            "2026-01-01",
            "USDT",
            1,
            100,
            value_brl_ptax=100,
            earn_type="FLEXIBLE",
        )
        for index in range(10)
    ]
    summary = summarize_earn(records)
    assert summary.by_type_brl == {"FLEXIBLE": 1_000}
    assert summary.total_brl == 1_000
