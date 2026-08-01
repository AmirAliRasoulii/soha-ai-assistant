#!/usr/bin/env bash
set -euo pipefail

# Resolve the repository root from the script location so the script works when
# invoked from any working directory.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

PYTHON="${PYTHON:-python3}"

echo "[verify] checking Python syntax"
"${PYTHON}" -m compileall -q src tests

echo "[verify] running unit tests"
# src is added to the import path instead of installing the package, so the
# check needs no network access and no dependencies.
PYTHONPATH="${REPO_ROOT}/src" "${PYTHON}" -m unittest discover -s tests -t tests -v

echo "[verify] all checks passed"
