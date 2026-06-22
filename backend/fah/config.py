"""Configuration loader.

Reads ``config/settings.yaml`` once and exposes a typed :class:`Settings` object. No path is
hardcoded in application code — everything resolves from here, relative to the project root.
Selected values may be overridden by environment variables (see ``.env.example``).
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

# Project root = .../fah-explorer  (this file is backend/fah/config.py)
PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]
SETTINGS_PATH: Path = PROJECT_ROOT / "config" / "settings.yaml"

logger = logging.getLogger("fah.config")


def _resolve(path_str: str) -> Path:
    """Resolve a settings path relative to the project root (absolute paths pass through)."""
    p = Path(path_str)
    return p if p.is_absolute() else (PROJECT_ROOT / p)


@dataclass(frozen=True)
class Settings:
    """Typed view over settings.yaml with environment overrides applied."""

    raw: dict[str, Any]
    app_name: str
    version: str
    log_level: str
    # paths (resolved, absolute)
    data_dir: Path
    uploads_dir: Path
    extracted_dir: Path
    exports_dir: Path
    database_path: Path
    database_url: str
    # crs
    crs_input_default: str
    crs_storage: str
    # extraction
    extraction_model: str
    extraction_prompt_version: str
    ocr_enabled: bool
    ocr_language: str
    require_human_review: bool
    # gis
    colors: dict[str, str] = field(default_factory=dict)
    rules_translation: Path = PROJECT_ROOT / "config" / "translation_rules.yaml"
    rules_risk: Path = PROJECT_ROOT / "config" / "risk_rules.yaml"

    def ensure_dirs(self) -> None:
        """Create the data directories if they do not yet exist."""
        for d in (self.data_dir, self.uploads_dir, self.extracted_dir, self.exports_dir):
            d.mkdir(parents=True, exist_ok=True)


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(
            f"Settings file not found: {path}. Expected at config/settings.yaml."
        )
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Settings file {path} did not parse to a mapping.")
    return data


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load and cache settings. Environment variables override selected fields."""
    raw = _load_yaml(SETTINGS_PATH)

    paths = raw.get("paths", {})
    db = raw.get("database", {})
    crs = raw.get("crs", {})
    extraction = raw.get("extraction", {})
    ocr = extraction.get("ocr", {})
    gis = raw.get("gis", {})
    rules = raw.get("rules", {})

    database_path = _resolve(paths.get("database", "data/fah_explorer.db"))
    # Derive the URL from the resolved absolute path so the DB lands in the project tree
    # regardless of the CWD uvicorn is launched from. DB_URL env var still overrides.
    database_url = os.environ.get("DB_URL", f"sqlite:///{database_path}")

    settings = Settings(
        raw=raw,
        app_name=raw.get("app", {}).get("name", "FAH Explorer"),
        version=raw.get("app", {}).get("version", "0.1.0"),
        log_level=os.environ.get("FAH_LOG_LEVEL", raw.get("app", {}).get("log_level", "INFO")),
        data_dir=_resolve(paths.get("data_dir", "data")),
        uploads_dir=_resolve(paths.get("uploads_dir", "data/uploads")),
        extracted_dir=_resolve(paths.get("extracted_dir", "data/extracted")),
        exports_dir=_resolve(paths.get("exports_dir", "data/exports")),
        database_path=database_path,
        database_url=database_url,
        crs_input_default=crs.get("input_default", "EPSG:32640"),
        crs_storage=crs.get("storage", "EPSG:4326"),
        extraction_model=os.environ.get(
            "FAH_EXTRACTION_MODEL", extraction.get("model", "claude-opus-4-8")
        ),
        extraction_prompt_version=extraction.get("prompt_version", "extract-v1"),
        ocr_enabled=bool(ocr.get("enabled", True)),
        ocr_language=os.environ.get("FAH_OCR_LANGUAGE", ocr.get("language", "eng")),
        require_human_review=bool(extraction.get("require_human_review", True)),
        colors=gis.get("colors", {}),
        rules_translation=_resolve(rules.get("translation", "config/translation_rules.yaml")),
        rules_risk=_resolve(rules.get("risk", "config/risk_rules.yaml")),
    )
    return settings


def configure_logging(level: str | None = None) -> None:
    """Configure root logging once, from settings (or an explicit level)."""
    lvl = (level or get_settings().log_level).upper()
    logging.basicConfig(
        level=getattr(logging, lvl, logging.INFO),
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )
