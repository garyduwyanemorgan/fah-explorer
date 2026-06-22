# FAH Explorer — v1.0.0

**Forensic Asset Hydrogeology Explorer** — transforms archived GCC geotechnical reports into
groundwater behaviour and asset-risk intelligence for forensic investigations.

> Core IP — the **translation layer**:
> `Geotechnical Data → Hydrostratigraphy → Groundwater Behaviour → Asset Risk`

Every risk score carries a **level**, a **confidence percentage**, the **evidence used**, and a
plain-language **hydrogeological explanation**. All outputs are traceable back to the source
document (forensic chain of custody).

---

## Quick start (local)

```bash
git clone <repo>
cd fah-explorer
pip install -e .
cp .env.example .env          # add ANTHROPIC_API_KEY and FAH_PASSWORD
python scripts/init_db.py     # create schema + seed lithology dictionary
bash scripts/start.sh         # Linux/macOS
.\scripts\start.ps1           # Windows PowerShell
# open http://localhost:8000
```

---

## Production deployment

### Docker (recommended)

```bash
cp .env.example .env
# Edit .env — set ANTHROPIC_API_KEY and FAH_PASSWORD (required for auth)

docker compose up -d
# open http://your-server:8000
```

The `fah-data` Docker volume persists the SQLite database and uploaded PDFs across restarts.

### Direct (Windows Server / Linux)

```bash
# Windows
.\scripts\start.ps1 -Port 8000 -Workers 2

# Linux/macOS
bash scripts/start.sh 8000 2
```

Put Nginx or Caddy in front for TLS termination. Example Nginx block:

```nginx
server {
    listen 443 ssl;
    server_name fah.yourdomain.com;

    ssl_certificate     /etc/ssl/certs/fah.crt;
    ssl_certificate_key /etc/ssl/private/fah.key;

    client_max_body_size 60M;          # matches the 50 MB upload limit

    location / {
        proxy_pass         http://127.0.0.1:8000;
        proxy_read_timeout 120s;       # accommodates LLM extraction calls
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
    }
}
```

---

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes (LLM extraction) | Claude API key (`sk-ant-…`) |
| `FAH_PASSWORD` | **Yes (production)** | Web UI password — all routes require it when set. Leave unset for local dev. |
| `DB_URL` | No | Override SQLite with PostGIS: `postgresql+psycopg://user:pass@host/db` |
| `FAH_EXTRACTION_MODEL` | No | Default: `claude-opus-4-8` |
| `FAH_OCR_LANGUAGE` | No | Tesseract language code, default `eng` |
| `FAH_LOG_LEVEL` | No | `DEBUG` / `INFO` / `WARNING` / `ERROR` |

---

## Backup

```bash
# Windows — run daily via Task Scheduler
.\scripts\backup_db.ps1

# Linux/macOS — add to crontab (2 AM daily)
0 2 * * * /path/to/fah-explorer/scripts/backup_db.sh
```

Backups land in `data/backups/` with timestamps; the last 30 are retained automatically.

---

## The workflow

```
Upload PDF
  → Run extraction (Claude + OCR)
  → Human review & approve (forensic gate — nothing commits without explicit approval)
  → Translation: raw lithology → hydrostratigraphy (aquifer / aquitard / barrier / perching)
  → Risk scoring: 10 categories, each with score + level + confidence + plain-language explanation
  → Interactive map: interpolated risk surfaces over satellite imagery
  → Export: KMZ (Google Earth) + forensic PDF report
```

---

## Running tests

```bash
python -m pytest                    # 66 tests
python -m pytest tests/ -v          # verbose
python -m mypy backend/             # type checking
```

---

## Architecture

```
fah-explorer/
├── backend/fah/
│   ├── api/          # FastAPI routes + auth middleware
│   ├── db/           # SQLAlchemy models, session, migrations, seed
│   ├── ingest/       # PDF reader, LLM extractor, human-review gate
│   ├── translate/    # Lithology → hydrostratigraphy (core IP)
│   ├── risk/         # 10-category risk engine (core IP)
│   ├── gis/          # Interpolation, surface build, KMZ export, PNG render
│   └── reports/      # Forensic PDF report generation
├── config/
│   ├── settings.yaml           # all runtime config
│   ├── translation_rules.yaml  # hydrostratigraphic translation IP
│   └── risk_rules.yaml         # risk scoring IP
├── frontend/         # Jinja2 templates + Leaflet map + static assets
├── data/             # uploads (immutable) · extracted · exports · SQLite DB
├── docs/             # full design documentation
├── scripts/          # start, backup, init_db, demo scripts
└── tests/            # 66 tests across all modules
```

---

## Version history

| Version | Date | Summary |
|---------|------|---------|
| **1.0.0** | 2026-06-22 | Market release — auth, data integrity fixes, performance, Docker |
| 0.1.0 | 2026-06-22 | MVP: full charter loop (Sprints 0–6) |

---

## License / use

Built for GCC forensic hydrogeology investigations. Outputs are reproducible and defensible:
raw reports are archived immutably and every derived value is traceable to its source document.
