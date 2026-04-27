#!/usr/bin/env bash

# Exit immediately on any failing command or unset variable usage.
set -euo pipefail

# Resolve repository root from script location for safe path handling.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Move to repository root before environment setup.
cd "${REPO_ROOT}"

# Create isolated virtual environment if it does not already exist.
if [[ ! -d ".venv" ]]; then
  python -m venv .venv
fi

# Activate the project virtual environment for dependency installation.
source ".venv/bin/activate"

# Install all project dependencies from requirements manifest.
python -m pip install --upgrade pip
pip install -r requirements.txt

# Copy example environment file only when local .env is absent.
if [[ -f ".env.example" && ! -f ".env" ]]; then
  cp ".env.example" ".env"
fi

# Initialize or migrate database schema to latest revision.
alembic upgrade head

# Emit setup completion message for operator confirmation.
echo "Setup complete."
