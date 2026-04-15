#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

run_validation() {
  local python_bin="$1"
  local venv_dir="$2"

  if ! command -v "$python_bin" >/dev/null 2>&1; then
    echo "[skip] ${python_bin} not found"
    return 0
  fi

  echo "[info] validating with ${python_bin}"
  "$python_bin" --version
  if [[ ! -x "${venv_dir}/bin/python" ]]; then
    "$python_bin" -m venv "$venv_dir"
  fi
  if ! "$venv_dir/bin/python" -c "import pdf2md, pytest" >/dev/null 2>&1; then
    "$venv_dir/bin/python" -m pip install --no-build-isolation -e '.[dev]'
  fi
  "$venv_dir/bin/python" -m pytest
  "$venv_dir/bin/python" -m pdf2md --help >/dev/null
}

run_validation python3.11 .venv311
run_validation python3.14 .venv314
