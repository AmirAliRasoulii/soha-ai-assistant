# ai-assistant

## Purpose

Foundation repository for a production-grade AI assistant. This commit contains
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
├── pyproject.toml
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

## Verification

```
./scripts/verify.sh
```

The script compiles all Python sources and runs the `unittest` suite. It
requires no network access and installs nothing.

## Process

- Git is the source of truth for all code and technical decisions.
- Notion is used only for project tracking and implementation reports.
