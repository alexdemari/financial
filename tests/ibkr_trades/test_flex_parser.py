"""Tests for flex_parser.py"""

from pathlib import Path

import pytest

from ibkr_trades.flex_parser import parse_flex_xml

_FLEX_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<FlexQueryResponse>
  <FlexStatements>
    <FlexStatement accountId="U1234567">
      <Trades>
        <Trade
          tradeID="111"
          tradeDate="2026-06-10"
          dateTime="2026-06-10;09:35:22"
          symbol="PEP   260717P00140000"
          underlyingSymbol="PEP"
          assetCategory="OPT"
          putCall="P"
          strike="140"
          expiry="20260717"
          quantity="-1"
          tradePrice="2.86"
          proceeds="286"
          ibCommission="-0.71"
          fifoPnlRealized="0"
          currency="USD"
          openCloseIndicator="O"
        />
        <Trade
          tradeID="222"
          tradeDate="2026-06-11"
          dateTime="2026-06-11;10:00:00"
          symbol="AAPL"
          underlyingSymbol="AAPL"
          assetCategory="STK"
          putCall=""
          strike=""
          expiry=""
          quantity="10"
          tradePrice="210.00"
          proceeds="-2100.00"
          ibCommission="-1.00"
          fifoPnlRealized=""
          currency="USD"
          openCloseIndicator="O"
        />
        <Trade
          tradeID="333"
          tradeDate="2026-06-12"
          dateTime="2026-06-12;11:00:00"
          symbol="CASH"
          underlyingSymbol=""
          assetCategory="CASH"
          quantity="1000"
          tradePrice="1"
          proceeds="1000"
          ibCommission="0"
          fifoPnlRealized="0"
          currency="USD"
          openCloseIndicator=""
        />
        <Trade
          tradeID="444"
          tradeDate="2026-06-13"
          dateTime="2026-06-13;09:00:00"
          symbol="AAPL  260717C00310000"
          underlyingSymbol="AAPL"
          assetCategory="OPT"
          putCall="C"
          strike="310"
          expiry="20260717"
          quantity="-1"
          tradePrice="1.50"
          proceeds="150"
          ibCommission="-0.71"
          fifoPnlRealized="0"
          currency="USD"
          openCloseIndicator="O"
        />
      </Trades>
    </FlexStatement>
  </FlexStatements>
</FlexQueryResponse>
"""


@pytest.fixture()
def flex_xml_path(tmp_path: Path) -> Path:
    p = tmp_path / "flex.xml"
    p.write_text(_FLEX_XML, encoding="utf-8")
    return p


def test_flex_parser_returns_opt_and_stk_trades(flex_xml_path):
    records = parse_flex_xml(flex_xml_path)
    asset_types = {r.asset_type for r in records}
    assert asset_types == {"OPT", "STK"}
    # CASH row must be excluded
    assert all(r.asset_type != "CASH" for r in records)


def test_flex_parser_maps_put_call_correctly(flex_xml_path):
    records = parse_flex_xml(flex_xml_path)
    opts = [r for r in records if r.asset_type == "OPT"]
    by_id = {r.trade_id: r for r in opts}
    assert by_id["111"].option_type == "PUT"
    assert by_id["444"].option_type == "CALL"


def test_flex_parser_sets_source_to_flex(flex_xml_path):
    records = parse_flex_xml(flex_xml_path)
    assert all(r.source == "flex" for r in records)


def test_flex_parser_expiry_formatted_as_iso(flex_xml_path):
    records = parse_flex_xml(flex_xml_path)
    opts = [r for r in records if r.asset_type == "OPT"]
    for r in opts:
        assert r.expiration == "2026-07-17"


def test_flex_parser_stk_has_no_option_fields(flex_xml_path):
    records = parse_flex_xml(flex_xml_path)
    stk = next(r for r in records if r.asset_type == "STK")
    assert stk.option_type is None
    assert stk.strike is None
    assert stk.expiration is None
