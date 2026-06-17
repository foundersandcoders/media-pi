#!/usr/bin/env bash
set -euo pipefail

if [[ "$OSTYPE" == "darwin"* ]]; then
  brew install pre-commit
else
  sudo apt-get update && sudo apt-get install -y pre-commit
fi

pre-commit install
echo "Done. pre-commit hooks installed."
