#!/usr/bin/with-contenv bashio
set -euo pipefail

export HEALTHHUB_VERSION="${HEALTHHUB_VERSION:-0.6.0}"
export HEALTHHUB_DATA_DIR="/data/healthhub"
export PYTHONPATH="/app${PYTHONPATH:+:${PYTHONPATH}}"

mkdir -p /data/healthhub
cd /app
alembic -c /app/alembic.ini upgrade head
exec uvicorn app.start:app --host 0.0.0.0 --port 8098 --proxy-headers --forwarded-allow-ips='*'
