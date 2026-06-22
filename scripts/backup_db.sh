#!/usr/bin/env bash
# Nightly SQLite backup — retains last 30 snapshots.
# Crontab:  0 2 * * * /path/to/fah-explorer/scripts/backup_db.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DB="$ROOT/data/fah_explorer.db"
BAKDIR="$ROOT/data/backups"
STAMP=$(date +"%Y%m%d_%H%M%S")

[ -f "$DB" ] || { echo "Database not found: $DB"; exit 1; }
mkdir -p "$BAKDIR"
cp "$DB" "$BAKDIR/fah_explorer_$STAMP.db"
echo "[backup] Saved $BAKDIR/fah_explorer_$STAMP.db"

# Rotate: keep only 30 most recent
ls -t "$BAKDIR"/fah_explorer_*.db 2>/dev/null | tail -n +31 | xargs -r rm --
echo "[backup] Done."
