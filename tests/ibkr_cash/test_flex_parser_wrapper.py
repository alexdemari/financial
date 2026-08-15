from __future__ import annotations

from pathlib import Path

from ibkr_cash.flex_parser import parse_nav_changes

_WRAPPED_NAV_XML = b"""\
<FlexQueryResponse>
<FlexStatements>
<FlexStatement accountId="U0000000">
<ChangeInNAV>
<ChangeInNAV fromDate="20260101" toDate="20260131"
  startingValue="100000.00" endingValue="106063.54" depositsWithdrawals="5000.00" />
</ChangeInNAV>
</FlexStatement>
</FlexStatements>
</FlexQueryResponse>
"""


def test_parse_nav_changes_skips_attribute_less_wrapper(tmp_path: Path) -> None:
    path = tmp_path / "wrapped.xml"
    path.write_bytes(_WRAPPED_NAV_XML)

    records = parse_nav_changes(path)

    assert len(records) == 1
    assert records[0].starting_value == 100000.00
    assert records[0].ending_value == 106063.54
