"""Forensic PDF report — per-project risk dossier (reportlab).

Sections: title + site metadata, methodology/provenance note, borehole summary, a colour-coded
risk matrix, a per-borehole "explain why" breakdown, and a risk-surface snapshot. Reads committed
``risk_results`` (run /risk first). See docs/08 (Export formats).
"""

from __future__ import annotations

import datetime as dt
import logging
import tempfile
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from fah.config import get_settings
from fah.db.models import Borehole, Project, RiskResult
from fah.gis.render import score_grid_to_png
from fah.risk.rules import get_risk_rules

logger = logging.getLogger("fah.reports.pdf")


class ReportError(RuntimeError):
    """Raised when a report cannot be produced (e.g. no risk results)."""


def _level_colour(level: str):
    return colors.HexColor(get_settings().colors.get(level, "#dddddd"))


def build_report(
    db: Session, project_id: int, out_dir: Path, surfaces=None, map_category: str = "rise"
) -> Path:
    project = db.get(Project, project_id)
    if project is None:
        raise ReportError(f"Project {project_id} not found")

    rules = get_risk_rules()
    cats = [c.key for c in rules.categories]
    labels = {c.key: c.label for c in rules.categories}

    boreholes = list(db.scalars(select(Borehole).where(Borehole.project_id == project_id)
                                .order_by(Borehole.bh_ref)))
    results = db.scalars(
        select(RiskResult).join(Borehole, RiskResult.borehole_id == Borehole.id)
        .where(Borehole.project_id == project_id)
    ).all()
    if not results:
        raise ReportError("No risk results — run /risk for this project before exporting a report.")

    by_bh: dict[int, dict[str, RiskResult]] = {}
    for r in results:
        by_bh.setdefault(r.borehole_id, {})[r.category] = r
    engine_version = results[0].engine_version or ""

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"project{project_id}_forensic_report.pdf"
    doc = SimpleDocTemplate(str(out_path), pagesize=A4,
                            leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=16 * mm, bottomMargin=16 * mm,
                            title=f"FAH Explorer Report — {project.name}")
    st = getSampleStyleSheet()
    story: list = []

    # --- Title + metadata ---
    story.append(Paragraph("Forensic Asset Hydrogeology Report", st["Title"]))
    story.append(Paragraph(project.name or f"Project {project_id}", st["Heading2"]))
    meta = [
        ["Location", project.location or "—", "Developer", project.developer or "—"],
        ["Report date", str(project.report_date or "—"), "Input CRS", project.crs_input or "—"],
        ["Generated", dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "Engine", engine_version],
    ]
    mt = Table(meta, colWidths=[28 * mm, 56 * mm, 28 * mm, 56 * mm])
    mt.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.grey),
        ("TEXTCOLOR", (2, 0), (2, -1), colors.grey),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(mt)
    story.append(Spacer(1, 6 * mm))

    # --- Methodology / provenance ---
    story.append(Paragraph("Methodology &amp; provenance", st["Heading3"]))
    method_note = (
        "Risk is derived from geotechnical observations via the FAH translation layer "
        "(geotechnical data → hydrostratigraphy → groundwater behaviour → asset risk). Translation "
        f"and risk rules are versioned ({engine_version}). Each score carries a confidence "
        "reflecting evidence completeness; spatial surfaces interpolate physical drivers within the "
        "borehole data hull only (areas beyond available data are not assessed). Raw reports are "
        "archived immutably and every derived value is traceable to its source borehole."
    )
    story.append(Paragraph(method_note, st["BodyText"]))
    story.append(Spacer(1, 5 * mm))

    # --- Borehole summary ---
    story.append(Paragraph("Borehole summary", st["Heading3"]))
    head = ["Borehole", "Easting", "Northing", "Ground (m)", "GWL depth (m)", "GWL elev (m)"]
    rows = [head] + [[
        bh.bh_ref,
        _fmt(bh.easting), _fmt(bh.northing),
        _fmt(bh.ground_level_m), _fmt(bh.gwl_depth_m), _fmt(bh.gwl_elevation_m),
    ] for bh in boreholes]
    bt = Table(rows, repeatRows=1)
    bt.setStyle(_grid_style())
    story.append(bt)
    story.append(Spacer(1, 6 * mm))

    # --- Risk matrix (colour-coded levels) ---
    story.append(Paragraph("Risk matrix (level by category)", st["Heading3"]))
    header = ["Borehole"] + [labels[c].split()[0] for c in cats]
    matrix = [header]
    for bh in boreholes:
        row = [bh.bh_ref]
        for c in cats:
            rr = by_bh.get(bh.id, {}).get(c)
            row.append((rr.level[:4].upper() if rr else "—"))
        matrix.append(row)
    mtab = Table(matrix, repeatRows=1)
    mstyle = _grid_style(font_size=7)
    for ri, bh in enumerate(boreholes, start=1):
        for ci, c in enumerate(cats, start=1):
            rr = by_bh.get(bh.id, {}).get(c)
            if rr:
                mstyle.add("BACKGROUND", (ci, ri), (ci, ri), _level_colour(rr.level))
    mtab.setStyle(mstyle)
    story.append(mtab)
    story.append(Paragraph(
        "<font size=7>Cell colour: green = Low, yellow = Moderate, orange = High, red = Critical.</font>",
        st["BodyText"]))

    # --- Risk surface snapshot ---
    if surfaces is not None and map_category in surfaces.score_grids:
        png = score_grid_to_png(surfaces.score_grids[map_category])
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp.write(png)
            img_path = tmp.name
        story.append(Spacer(1, 6 * mm))
        story.append(Paragraph(f"Risk surface — {labels.get(map_category, map_category)}", st["Heading3"]))
        story.append(Image(img_path, width=120 * mm, height=120 * mm * surfaces.ny / max(surfaces.nx, 1)))
        story.append(Paragraph(
            f"<font size=7>Interpolation: {surfaces.method}; drivers: "
            f"{', '.join(surfaces.drivers_available)}. Uncoloured areas are outside the data hull "
            "(insufficient data).</font>", st["BodyText"]))

    # --- Per-borehole explanations (the 'explain why') ---
    story.append(PageBreak())
    story.append(Paragraph("Risk explanations by borehole", st["Heading2"]))
    for bh in boreholes:
        story.append(Paragraph(bh.bh_ref, st["Heading3"]))
        for c in cats:
            rr = by_bh.get(bh.id, {}).get(c)
            if not rr or rr.score == 0:
                continue
            story.append(Paragraph(
                f"<b>{labels[c]}</b> — {rr.level.capitalize()} "
                f"(score {rr.score}, confidence {rr.confidence_pct}%)", st["BodyText"]))
            expl = (rr.explanation or "").replace("\n", "<br/>").replace("•", "&bull;")
            story.append(Paragraph(f"<font size=8>{expl}</font>", st["BodyText"]))
            story.append(Spacer(1, 2 * mm))
        story.append(Spacer(1, 4 * mm))

    doc.build(story)
    logger.info("Wrote forensic PDF %s", out_path)
    return out_path


def _fmt(v) -> str:
    return "—" if v is None else f"{v:.2f}" if isinstance(v, float) else str(v)


def _grid_style(font_size: int = 8) -> TableStyle:
    return TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), font_size),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f1c24")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#b0b8bf")),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (0, -1), [colors.white, colors.HexColor("#f2f5f7")]),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ])
