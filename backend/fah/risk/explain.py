"""Plain-language explanation builder — the charter's 'explain why' requirement."""

from __future__ import annotations

from typing import Any


def humanize(factor_id: str) -> str:
    return factor_id.replace("_", " ").capitalize()


def factor_sentence(factor_id: str, value: Any, reliability: str) -> str:
    """One bullet line for a fired factor, with its value and reliability tag."""
    if value is None or isinstance(value, bool):
        return f"{humanize(factor_id)} ({reliability})"
    return f"{humanize(factor_id)}: {value} ({reliability})"


def build_explanation(
    label: str,
    score: int,
    level: str,
    confidence_pct: int,
    fired: list[dict[str, Any]],
) -> str:
    """Assemble the charter-style explanation block."""
    header = f"{label} Risk = {level.capitalize()} (score {score}, confidence {confidence_pct}%)"
    if not fired:
        return header + "\nNo risk factors triggered with the available evidence."
    lines = [header, "Reason:"]
    for f in fired:
        lines.append(" • " + factor_sentence(f["id"], f.get("value"), f["reliability"]))
    return "\n".join(lines)
