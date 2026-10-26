#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
fi
.venv/bin/pip install -r requirements-lock.txt
.venv/bin/pip install --no-deps --no-build-isolation -e .
(cd web && npm ci && npm run build)
printf '\nLENS-GUARD: http://127.0.0.1:8765\nNo wireless capture will be started.\n'
exec .venv/bin/python -m lens_guard serve
