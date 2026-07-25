# Contributing

This project is currently an early-stage open-source project.

## Development setup

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

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
