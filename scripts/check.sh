#!/usr/bin/env bash
# Run every local gate. Needs uv (for uvx) and, for the last two, hermes.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

uvx ruff check .
uvx --with pyyaml --with requests --with youtube-transcript-api==1.2.4 pytest -q

if command -v hermes >/dev/null; then
  hermes plugins doctor . --ci
  hermes plugins validate . --install-deps
else
  echo "hermes not on PATH: skipped doctor and validate" >&2
fi
