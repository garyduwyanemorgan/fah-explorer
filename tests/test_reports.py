"""Sprint 6 — forensic PDF report generation."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from fah.db.models import Borehole, LabResult, Layer, Project
from fah.gis.surface import build_surfaces
from fah.reports import pdf_report
from fah.risk.engine import assess_project
from fah.translate.pipeline import translate_project

_E0, _N0 = 500_000.0, 2_700_000.0


def _make_site(db: Session, n_side: int = 3) -> Project:
    project = Project(name="Report Site", location="Dubai", developer="ACME",
                      crs_input="EPSG:32640")
    db.add(project); db.flush()
    k = 0
    for i in range(n_side):
        for j in range(n_side):
            k += 1
            bh = Borehole(project_id=project.id, bh_ref=f"BH-{k:02d}",
                          easting=_E0 + i * 100, northing=_N0 + j * 100,
                          ground_level_m=3.0, gwl_depth_m=1.2 + 0.2 * (i + j))
            db.add(bh); db.flush()
            db.add(Layer(borehole_id=bh.id, seq=1, top_depth_m=0.0, bottom_depth_m=2.0,
                         raw_description="Brown SAND, loose", spt_n=6))
            db.add(Layer(borehole_id=bh.id, seq=2, top_depth_m=2.0, bottom_depth_m=5.0,
                         raw_description="Grey SABKHA, gypsiferous", spt_n=None))
            db.add(LabResult(borehole_id=bh.id, depth_m=1.5, parameter="chloride",
                             value=6000, unit="mg/L"))
    db.commit()
    return project


def test_pdf_report_with_surface(db: Session, tmp_path) -> None:
    project = _make_site(db)
    translate_project(db, project.id); db.commit()
    assess_project(db, project.id); db.commit()
    surfaces = build_surfaces(db, project.id)

    path = pdf_report.build_report(db, project.id, tmp_path, surfaces, "rise")
    assert path.exists()
    data = path.read_bytes()
    assert data[:5] == b"%PDF-"          # valid PDF
    assert len(data) > 3000              # has real content (tables + image)


def test_pdf_report_without_surface(db: Session, tmp_path) -> None:
    # Few boreholes -> no surface; report must still generate (tables + explanations).
    project = Project(name="Small", crs_input="EPSG:32640"); db.add(project); db.flush()
    bh = Borehole(project_id=project.id, bh_ref="BH-1", easting=_E0, northing=_N0, gwl_depth_m=1.5)
    db.add(bh); db.flush()
    db.add(Layer(borehole_id=bh.id, seq=1, top_depth_m=0.0, bottom_depth_m=4.0,
                 raw_description="Grey SABKHA", spt_n=None))
    db.commit()
    translate_project(db, project.id); db.commit()
    assess_project(db, project.id); db.commit()

    path = pdf_report.build_report(db, project.id, tmp_path, surfaces=None)
    assert path.read_bytes()[:5] == b"%PDF-"


def test_pdf_report_requires_risk_results(db: Session, tmp_path) -> None:
    project = Project(name="NoRisk", crs_input="EPSG:32640"); db.add(project); db.flush()
    db.add(Borehole(project_id=project.id, bh_ref="BH-1", easting=_E0, northing=_N0))
    db.commit()
    with pytest.raises(pdf_report.ReportError):
        pdf_report.build_report(db, project.id, tmp_path)
