"""Sprint 5 — GIS: render mask, driver interpolation, risk surfaces, GeoJSON, KMZ."""

from __future__ import annotations

import numpy as np
from sqlalchemy.orm import Session

from fah.db.models import Borehole, LabResult, Layer, Project
from fah.gis import export, layers, render
from fah.gis.domains import build_grid
from fah.gis.surface import build_surfaces
from fah.risk.engine import assess_project
from fah.translate.pipeline import translate_project

# UTM 40N coordinates (~24.4N, 57E) for a small synthetic site.
_E0, _N0 = 500_000.0, 2_700_000.0


def _make_site(db: Session, n_side: int = 3, spacing: float = 100.0) -> Project:
    project = Project(name="Grid Site", crs_input="EPSG:32640")
    db.add(project); db.flush()
    k = 0
    for i in range(n_side):
        for j in range(n_side):
            k += 1
            bh = Borehole(
                project_id=project.id, bh_ref=f"BH-{k:02d}",
                easting=_E0 + i * spacing, northing=_N0 + j * spacing,
                ground_level_m=3.0, gwl_depth_m=1.2 + 0.2 * (i + j),
            )
            db.add(bh); db.flush()
            db.add(Layer(borehole_id=bh.id, seq=1, top_depth_m=0.0, bottom_depth_m=2.0,
                         raw_description="Brown SAND, loose", spt_n=6))
            db.add(Layer(borehole_id=bh.id, seq=2, top_depth_m=2.0, bottom_depth_m=5.0,
                         raw_description="SABKHA, gypsiferous" if (i + j) % 2 else
                         "Weakly cemented SANDSTONE", spt_n=None))
            db.add(LabResult(borehole_id=bh.id, depth_m=1.5, parameter="chloride",
                             value=3000 + 600 * (i + j), unit="mg/L"))
    db.commit()
    return project


def test_build_grid_and_mask() -> None:
    xs = np.array([0.0, 100.0, 100.0, 0.0, 50.0])
    ys = np.array([0.0, 0.0, 100.0, 100.0, 50.0])
    grid = build_grid(xs, ys, resolution_m=10.0)
    assert grid is not None
    assert grid.inside.any() and not grid.inside.all()  # some cells masked out


def test_build_surfaces_full_pipeline(db: Session) -> None:
    project = _make_site(db, n_side=3)
    translate_project(db, project.id); db.commit()
    assess_project(db, project.id); db.commit()

    surfaces = build_surfaces(db, project.id)
    assert surfaces is not None
    assert surfaces.n_boreholes == 9
    assert "rise" in surfaces.score_grids

    rise = surfaces.score_grids["rise"]
    assert rise.shape == (surfaces.ny, surfaces.nx)
    assert np.isnan(rise).any()        # masked outside the hull
    assert np.isfinite(rise).any()     # scored inside the hull
    finite = rise[np.isfinite(rise)]
    assert finite.min() >= 0 and finite.max() <= 100

    conf = surfaces.confidence_grid
    cfin = conf[np.isfinite(conf)]
    assert cfin.min() >= 0 and cfin.max() <= 100

    # bounds are sane WGS84 for UTM 40N.
    south, west, north, east = surfaces.bounds
    assert south < north and west < east
    assert 20 < south < 30 and 50 < west < 60


def test_render_png_signature(db: Session) -> None:
    project = _make_site(db, n_side=3)
    translate_project(db, project.id); db.commit()
    surfaces = build_surfaces(db, project.id)
    png = render.score_grid_to_png(surfaces.score_grids["rise"])
    assert png[:8] == b"\x89PNG\r\n\x1a\n"     # valid PNG header
    conf_png = render.confidence_grid_to_png(surfaces.confidence_grid)
    assert conf_png[:8] == b"\x89PNG\r\n\x1a\n"


def test_borehole_geojson(db: Session) -> None:
    project = _make_site(db, n_side=3)
    translate_project(db, project.id); db.commit()
    assess_project(db, project.id); db.commit()
    gj = layers.borehole_geojson(db, project.id, "rise")
    assert gj["type"] == "FeatureCollection"
    assert len(gj["features"]) == 9
    props = gj["features"][0]["properties"]
    assert "level" in props and "color" in props and "explanation" in props


def test_export_kmz(db: Session, tmp_path) -> None:
    project = _make_site(db, n_side=3)
    translate_project(db, project.id); db.commit()
    assess_project(db, project.id); db.commit()
    path = export.export_kmz(db, project.id, "salinity", tmp_path)
    assert path.exists() and path.stat().st_size > 1000   # contains overlay + placemarks


def test_insufficient_boreholes_no_surface(db: Session) -> None:
    project = Project(name="Sparse", crs_input="EPSG:32640")
    db.add(project); db.flush()
    for k in range(3):
        db.add(Borehole(project_id=project.id, bh_ref=f"BH-{k}",
                        easting=_E0 + k * 50, northing=_N0, gwl_depth_m=1.5))
    db.commit()
    assert build_surfaces(db, project.id) is None
