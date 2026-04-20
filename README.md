# Financial Project

Python financial tooling project with modular packages under `src/`.

Current modules include:

- `stock_data_manager`
- `stock_analyzer`
- `options_tech_scanner`

## Documentation

- [Stock Data Manager README](src/stock_data_manager/README.md)
- [Architecture Docs](docs/arquitecture)
- [Agent Context](AGENTS.md)

Note: the architecture docs directory is currently named `docs/arquitecture`.

## Environment

This project is normally run from PyCharm Terminal using Ubuntu/WSL.

Common commands:

```bash
uv sync --dev
.venv/bin/python -m pytest tests/stock_data_manager
just --list
```

PowerShell can be used for file inspection and editing, but Python, `uv`, and pre-commit may fail there because the virtualenv and Git hooks are WSL-oriented.
