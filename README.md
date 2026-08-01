# ai-assistant

## Purpose

Foundation repository for a production-grade AI assistant. This branch contains
only the minimal skeleton needed to develop, test, and review future changes
through Git.

## Status

Foundation only. No AI, retrieval, API, database, container, or deployment
functionality is implemented yet. Standard library only; no external
dependencies.

## Structure

```
ai-assistant/
├── README.md
├── .gitignore
├── .python-version
├── pyproject.toml
├── uv.lock
├── src/
│   └── ai_assistant/
│       ├── __init__.py
│       └── system_info.py
├── tests/
│   └── test_system_info.py
└── scripts/
    └── verify.sh
```

## Language conventions

- Source code, identifiers, comments, logs, commit messages, and technical
  documentation are in English.
- User-facing content will be Persian.
- Comments explain only non-obvious decisions or constraints.

## Local setup

```
uv sync --locked
./scripts/verify.sh
```

- `uv` is the only environment and dependency manager for this project.
- `uv` creates and manages the project-local `.venv`; activating it is not
  required, because `uv run` selects it automatically.
- `uv.lock` is committed and must stay in sync with `pyproject.toml`.
- Add dependencies with `uv add`; never use `conda install`, `pip install`,
  `uv pip install`, or `--active` for project dependencies.
- The project is installed as a package, so `import ai_assistant` must work
  without setting `PYTHONPATH`.

## Quality checks

```
./scripts/verify.sh
```

The script runs Ruff formatting, Ruff linting, mypy strict type checking,
pytest, and branch coverage with a minimum threshold. Tool settings live in
`pyproject.toml`.

## Process

- Git is the source of truth for all code and technical decisions.
- Notion is used only for project tracking and implementation reports.
