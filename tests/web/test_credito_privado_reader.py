from datetime import date

import pytest

from web.readers import credito_privado_reader


class _FixedDate(date):
    @classmethod
    def today(cls):
        return cls(2026, 8, 16)


def _write_config(tmp_path, content: str) -> None:
    config_path = tmp_path / "credito_privado.yaml"
    config_path.write_text(content, encoding="utf-8")
    credito_privado_reader.CONFIG_PATH = config_path


def test_read_credito_privado_returns_empty_when_file_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(
        credito_privado_reader, "CONFIG_PATH", tmp_path / "missing.yaml"
    )

    assert credito_privado_reader.read_credito_privado() == []


def test_valor_atual_falls_back_to_valor_investido_when_null(tmp_path):
    _write_config(
        tmp_path,
        """
items:
  - id: cdb-1
    valor_investido: 10000
    valor_atual: null
    vencimento: "2027-01-01"
""",
    )

    [item] = credito_privado_reader.read_credito_privado()

    assert item.valor_atual == 10000
    assert item.valor_estimado is True


def test_valor_atual_used_directly_when_present(tmp_path):
    _write_config(
        tmp_path,
        """
items:
  - id: cdb-1
    valor_investido: 10000
    valor_atual: 10350.75
    vencimento: "2027-01-01"
""",
    )

    [item] = credito_privado_reader.read_credito_privado()

    assert item.valor_atual == pytest.approx(10350.75)
    assert item.valor_estimado is False


def test_item_marked_vencido_when_vencimento_in_past(monkeypatch, tmp_path):
    _write_config(
        tmp_path,
        """
items:
  - id: cdb-1
    valor_investido: 5000
    vencimento: "2026-08-15"
""",
    )
    monkeypatch.setattr(credito_privado_reader, "date", _FixedDate)

    [item] = credito_privado_reader.read_credito_privado()

    assert item.status == "vencido"


def test_total_excludes_vencido_items(monkeypatch, tmp_path):
    _write_config(
        tmp_path,
        """
items:
  - id: active
    valor_atual: 10000
    vencimento: "2027-01-01"
  - id: expired
    valor_atual: 5000
    vencimento: "2026-08-15"
""",
    )
    monkeypatch.setattr(credito_privado_reader, "date", _FixedDate)

    items = credito_privado_reader.read_credito_privado()

    assert credito_privado_reader.total_credito_privado_brl(items) == 10000


def test_missing_valor_investido_treated_as_zero(tmp_path):
    _write_config(
        tmp_path,
        """
items:
  - id: missing-value
    vencimento: "2027-01-01"
  - id: normal
    valor_investido: 2500
    vencimento: "2027-01-01"
""",
    )

    items = credito_privado_reader.read_credito_privado()

    assert [item.valor_investido for item in items] == [0.0, 2500.0]
    assert credito_privado_reader.total_credito_privado_brl(items) == 2500
