from dataclasses import dataclass


@dataclass
class ScannerRow:
    symbol: str
    close: float | None
    avg_volume_20: float | None
    market_cap: float | None
    ranking_mode: str | None
    lux_signal: str | None
    lux_options_hint: str | None
    lux_context: str | None
    lux_trend: str | None
    lux_strength: str | None
    lux_adx: float | None
    lux_last_event: str | None
    lux_last_event_options_hint: str | None
    lux_last_event_context: str | None
    lux_last_event_date: str | None
    lux_days_since_last_event: int | None
    lux_active_event: str | None
    lux_active_event_options_hint: str | None
    lux_active_event_context: str | None
    lux_active_event_date: str | None
    lux_days_since_active_event: int | None
    smc_signal: str | None
    smc_options_hint: str | None
    smc_context: str | None
    smc_bias: str | None
    smc_range_position_pct: float | None
    smc_rsi: float | None
    smc_last_event: str | None
    smc_last_event_options_hint: str | None
    smc_last_event_context: str | None
    smc_last_event_date: str | None
    smc_days_since_last_event: int | None
    smc_active_event: str | None
    smc_active_event_options_hint: str | None
    smc_active_event_context: str | None
    smc_active_event_date: str | None
    smc_days_since_active_event: int | None
    alignment: str | None
    consistency_score: int | None
    market_state: str | None
    adjusted_alignment: str | None
    action_bucket: str | None
    eligible: bool
    excluded_reason: str | None
