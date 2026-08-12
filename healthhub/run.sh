#!/usr/bin/with-contenv bashio
set -euo pipefail

export HEALTHHUB_VERSION="${BUILD_VERSION:-0.1.0}"
export HEALTHHUB_ENFORCE_INGRESS="true"
export HEALTHHUB_DATA_DIR="/data/healthhub"
export PYTHONPATH="/app${PYTHONPATH:+:${PYTHONPATH}}"

mkdir -p /data/healthhub
cd /app
alembic -c /app/alembic.ini upgrade head
exec uvicorn app.main:app --host 0.0.0.0 --port 8098 --proxy-headers --forwarded-allow-ips='*'
