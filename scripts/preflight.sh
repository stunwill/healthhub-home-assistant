#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

printf '\n== Backend ==\n'
cd "$ROOT_DIR/healthhub"
python -m pip install -r requirements-dev.txt
ruff check app tests
mypy app
pytest --cov=app --cov-report=term-missing

printf '\n== Frontend ==\n'
cd "$ROOT_DIR/healthhub/frontend"
npm install --no-audit --no-fund
npm run lint
npm run build

printf '\n== Home Assistant container ==\n'
cd "$ROOT_DIR"
BUILD_VERSION="$(awk -F'"' '/^version:/ {print $2}' healthhub/config.yaml)"
docker build \
  --build-arg BUILD_ARCH=amd64 \
  --build-arg BUILD_VERSION="$BUILD_VERSION" \
  -t healthhub:preflight \
  ./healthhub

printf '\nPreflight passed. Home Assistant add-on linting runs in GitHub Actions.\n'
