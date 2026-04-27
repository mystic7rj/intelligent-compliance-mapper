#!/usr/bin/env bash

# Exit on command failure, unset variables, or failed pipelines.
set -euo pipefail

# Resolve repository root from script location for deterministic execution.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Change to repository root before activating environment.
cd "${REPO_ROOT}"

# Activate local virtual environment for reproducible tooling.
source ".venv/bin/activate"

# Run full test suite with coverage threshold enforcement.
if python -m pytest tests/ --cov=src --cov-fail-under=85; then
  # Print pass summary when all quality gates are satisfied.
  echo "Test suite passed with coverage >= 85%."
else
  # Print failure summary when tests or coverage gates fail.
  echo "Test suite failed or coverage dropped below 85%."
  exit 1
fi
