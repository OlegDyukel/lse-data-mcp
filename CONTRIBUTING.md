# Contributing

This project is currently an early-stage open-source project.

## Development setup

Python 3.11 or newer is required. macOS ships an older `python3`, so check before creating the
environment and use a supported interpreter by name if needed — `brew install python@3.13`, then
`python3.13`. On Windows, use `py -3.13`.

```bash
git clone https://github.com/OlegDyukel/lse-data-mcp.git
cd lse-data-mcp

python3 --version               # must be 3.11 or newer
python3 -m venv .venv           # or python3.13 -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

To use the server rather than work on it, no clone is needed: see the
[README](README.md#installation).

## Before submitting changes

```bash
ruff format .
ruff check .
mypy src tests
pytest
```

Keep the adapter thin and read-only. New tools should:

1. map directly to a documented upstream SDK method;
2. use explicit input and return types;
3. avoid caching or persisting provider data;
4. include mocked tests;
5. translate upstream errors without exposing credentials.
