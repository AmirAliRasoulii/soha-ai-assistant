#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd -P)"
cd "${REPO_ROOT}"

# Inherited interpreter and environment variables from Conda or a parent shell
# would let uv resolve an environment other than the project .venv.
unset PYTHONPATH VIRTUAL_ENV CONDA_PREFIX CONDA_DEFAULT_ENV UV_PROJECT_ENVIRONMENT

if ! command -v uv >/dev/null 2>&1; then
	echo "[verify] error: uv was not found on PATH" >&2
	exit 1
fi

if [ ! -f "${REPO_ROOT}/uv.lock" ]; then
	echo "[verify] error: uv.lock is missing; run 'uv lock' first" >&2
	exit 1
fi

echo "[verify] checking lockfile"
uv lock --check

echo "[verify] syncing locked environment"
uv sync --locked

echo "[verify] checking interpreter location"
PYTHON_PATH="$(uv run --locked python -c 'import sys; print(sys.executable)')"
RESOLVED_PYTHON="$(cd "$(dirname "${PYTHON_PATH}")" && pwd -P)/$(basename "${PYTHON_PATH}")"
VENV_ROOT="$(cd "${REPO_ROOT}/.venv" && pwd -P)"
case "${RESOLVED_PYTHON}" in
	"${VENV_ROOT}"/*) ;;
	*)
		echo "[verify] error: interpreter is outside the project .venv: ${RESOLVED_PYTHON}" >&2
		exit 1
		;;
esac

echo "[verify] checking formatting"
uv run --locked ruff format --check .

echo "[verify] checking lint"
uv run --locked ruff check .

echo "[verify] checking types"
uv run --locked mypy src

echo "[verify] checking Python syntax"
uv run --locked python -m compileall -q src tests

echo "[verify] running tests with coverage"
uv run --locked pytest \
	--cov=ai_assistant \
	--cov-branch \
	--cov-report=term-missing \
	--cov-fail-under=95

echo "[verify] checking installed package import"
uv run --locked python -c "import ai_assistant"

echo "[verify] all checks passed"
