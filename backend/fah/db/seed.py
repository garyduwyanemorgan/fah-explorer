"""Seed reference data — the lithology dictionary — from translation_rules.yaml.

Keeps the operational DB's reference table in sync with the externalised IP. Re-runnable: upserts
by lithology code.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy.orm import Session

from fah.config import get_settings
from fah.db.models import LithologyDictionary

logger = logging.getLogger("fah.db.seed")


def _load_lithologies(rules_path: Path) -> dict[str, Any]:
    with rules_path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return data.get("lithologies", {})


def seed_lithology_dictionary(db: Session, rules_path: Path | None = None) -> int:
    """Upsert lithology dictionary rows from the translation rules. Returns row count."""
    settings = get_settings()
    path = rules_path or settings.rules_translation
    lithologies = _load_lithologies(path)

    count = 0
    for code, spec in lithologies.items():
        row = db.get(LithologyDictionary, code)
        if row is None:
            row = LithologyDictionary(code=code)
            db.add(row)
        row.canonical_name = spec.get("canonical_name", code.replace("_", " ").title())
        row.synonyms_json = json.dumps(spec.get("synonyms", []))
        row.default_k_h = spec.get("k_h")
        row.default_k_v = spec.get("k_v")
        row.storage_class = spec.get("storage")
        row.cemented_default = bool(spec.get("cemented_default", False))
        row.salinity_flag = bool(spec.get("salinity_flag", False))
        count += 1

    db.flush()
    logger.info("Seeded %d lithology dictionary entries from %s", count, path.name)
    return count
