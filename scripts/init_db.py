"""Create the database schema and seed reference data.

Usage:  python scripts/init_db.py
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

# Make the backend package importable when run as a script.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from fah.config import configure_logging  # noqa: E402
from fah.db.seed import seed_lithology_dictionary  # noqa: E402
from fah.db.session import init_db, session_scope  # noqa: E402


def main() -> None:
    configure_logging()
    log = logging.getLogger("fah.scripts.init_db")
    init_db()
    with session_scope() as db:
        n = seed_lithology_dictionary(db)
    log.info("Database initialised and seeded (%d lithologies).", n)


if __name__ == "__main__":
    main()
