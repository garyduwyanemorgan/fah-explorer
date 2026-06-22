#!/usr/bin/env bash
# Start FAH Explorer locally (Linux / macOS).
# Usage:  bash scripts/start.sh [port] [workers]
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PORT="${1:-8000}"
WORKERS="${2:-1}"

# Load .env if present
if [ -f "$ROOT/.env" ]; then
    set -a
    # shellcheck disable=SC1090
    source "$ROOT/.env"
    set +a
    echo "[fah] Loaded .env"
fi

if [ -z "${FAH_PASSWORD:-}" ]; then
    echo "[fah] WARNING: FAH_PASSWORD not set — running in unauthenticated dev mode."
fi

echo "[fah] Initialising database..."
python - <<EOF
import sys
sys.path.insert(0, "$ROOT/backend")
from fah.db.session import init_db
init_db()
EOF

echo "[fah] Starting FAH Explorer v1.0.0 on http://localhost:$PORT"
exec python -m uvicorn fah.main:app \
    --app-dir "$ROOT/backend" \
    --host 127.0.0.1 \
    --port "$PORT" \
    --workers "$WORKERS" \
    --timeout-keep-alive 75 \
    --log-level info
