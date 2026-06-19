"""LLM-assisted extraction — geotechnical report text → strict JSON via Anthropic Claude.

Design: the prompt builder and the JSON parser are **pure functions** (unit-testable with no API
key); only :func:`extract_text` performs the network call. The raw model output is preserved
verbatim for the audit trail. See docs/07_PDF_EXTRACTION_WORKFLOW.md (stage 3).
"""

from __future__ import annotations

import json
import logging
import os
import re

logger = logging.getLogger("fah.ingest.llm_extractor")

PROMPT_VERSION = "extract-v1"

_SYSTEM_PROMPT = """\
You are a geotechnical data extraction engine for a forensic hydrogeology platform.
Extract borehole information from the supplied geotechnical report text and return ONLY a single
JSON object — no prose, no markdown, no code fences.

Schema:
{
  "name": str|null, "location": str|null, "developer": str|null,
  "report_date": "YYYY-MM-DD"|null, "crs": "EPSG:xxxxx"|null,
  "boreholes": [
    {
      "bh_ref": str,
      "easting": float|null, "northing": float|null, "lon": float|null, "lat": float|null,
      "ground_level_m": float|null, "gwl_depth_m": float|null, "date_drilled": "YYYY-MM-DD"|null,
      "layers": [
        {"top_depth_m": float, "bottom_depth_m": float, "raw_description": str,
         "spt_n": int|null, "moisture": str|null, "density_desc": str|null}
      ],
      "lab_results": [
        {"depth_m": float|null, "parameter": str, "value": float|null, "unit": str|null}
      ]
    }
  ]
}

Rules:
- Use null when a value is absent. Do NOT invent or estimate values.
- Depths in metres; bottom_depth_m must be greater than top_depth_m.
- Preserve the verbatim soil description in raw_description.
- parameter names for lab_results use lowercase canonical terms where possible
  (chloride, sulphate, tds, ph, carbonate, organic_content).
- Return every borehole found in the document.
"""


class LlmNotConfigured(RuntimeError):
    """Raised when the Anthropic SDK or API key is unavailable."""


def build_messages(report_text: str) -> tuple[str, list[dict]]:
    """Return (system_prompt, messages) for the Messages API. Pure function."""
    user = (
        "Extract all borehole data from the following geotechnical report text and return the "
        "JSON object described in the system prompt.\n\n=== REPORT TEXT START ===\n"
        f"{report_text}\n=== REPORT TEXT END ==="
    )
    return _SYSTEM_PROMPT, [{"role": "user", "content": user}]


def parse_json_response(raw: str) -> dict:
    """Extract the JSON object from a model response, tolerating fences/prose. Pure function."""
    if not raw or not raw.strip():
        raise ValueError("Empty LLM response")
    text = raw.strip()
    # Strip ```json ... ``` fences if present.
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    # Fall back to the outermost {...} span.
    if not text.startswith("{"):
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("No JSON object found in LLM response")
        text = text[start : end + 1]
    return json.loads(text)


def extract_text(
    report_text: str,
    *,
    model: str,
    api_key: str | None = None,
    max_tokens: int = 8192,
) -> tuple[str, dict]:
    """Call Claude to extract structured data. Returns (raw_response_text, parsed_dict).

    Raises :class:`LlmNotConfigured` with actionable guidance if the SDK or key is missing.
    """
    try:
        from anthropic import Anthropic
    except Exception as exc:  # pragma: no cover - import guard
        raise LlmNotConfigured(
            "The 'anthropic' package is not installed. Run `pip install anthropic`."
        ) from exc

    key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise LlmNotConfigured(
            "ANTHROPIC_API_KEY is not set. Copy .env.example to .env and add your key "
            "(see docs/07_PDF_EXTRACTION_WORKFLOW.md)."
        )

    system, messages = build_messages(report_text)
    client = Anthropic(api_key=key)
    resp = client.messages.create(
        model=model, max_tokens=max_tokens, system=system, messages=messages
    )
    raw = "".join(block.text for block in resp.content if getattr(block, "type", None) == "text")
    logger.info("Claude extraction complete (model=%s, %d chars)", model, len(raw))
    return raw, parse_json_response(raw)
