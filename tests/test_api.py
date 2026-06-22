"""HTTP-layer tests — project-existence guards, category validation, and the happy-path loop.

These lock in the robustness contract: an unknown project id returns 404 (never an empty 200 that a
client can't distinguish from "exists but empty"), and the core read/compute routes behave.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from fah.db.models import Borehole, LabResult, Layer, Project
from fah.db.session import get_db
from fah.main import app
from fah.risk.engine import assess_project
from fah.translate.pipeline import translate_project

_E0, _N0 = 500_000.0, 2_700_000.0


@pytest.fixture()
def client(db: Session) -> Iterator[TestClient]:
    """TestClient bound to the in-memory `db` fixture (shared session across requests)."""
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _seed_scored_project(db: Session, n_side: int = 4) -> Project:
    project = Project(name="API Site", location="Dubai", crs_input="EPSG:32640")
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
                         raw_description="Grey SABKHA, gypsiferous"))
            db.add(LabResult(borehole_id=bh.id, depth_m=1.5, parameter="chloride",
                             value=6000, unit="mg/L"))
    db.commit()
    translate_project(db, project.id); db.commit()
    assess_project(db, project.id); db.commit()
    return project


# --- unknown project must 404 everywhere, not 200/empty -------------------------------------------

@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/projects/999/risk"),
        ("post", "/projects/999/risk"),
        ("post", "/projects/999/translate"),
        ("get", "/projects/999/layers/rise.geojson"),
        ("get", "/projects/999/surface/rise/meta"),
        ("get", "/projects/999/surface/rise.png"),
        ("get", "/projects/999/surface/rise/confidence.png"),
        ("get", "/projects/999/export/kmz?category=rise"),
        ("get", "/projects/999/export/pdf"),
        ("get", "/projects/999/map"),
        ("get", "/projects/999/workspace"),
    ],
)
def test_unknown_project_returns_404(client: TestClient, method: str, path: str) -> None:
    resp = getattr(client, method)(path)
    assert resp.status_code == 404, f"{method.upper()} {path} -> {resp.status_code}"


# --- category validation --------------------------------------------------------------------------

def test_unknown_category_returns_404(client: TestClient, db: Session) -> None:
    project = _seed_scored_project(db)
    resp = client.get(f"/projects/{project.id}/layers/not_a_category.geojson")
    assert resp.status_code == 404
    assert "Unknown category" in resp.json()["detail"]


# --- happy path -----------------------------------------------------------------------------------

def test_create_and_read_project(client: TestClient) -> None:
    created = client.post("/projects", json={"name": "Marina", "crs_input": "EPSG:32640"})
    assert created.status_code == 201
    pid = created.json()["id"]
    assert client.get(f"/projects/{pid}").json()["borehole_count"] == 0


def test_risk_and_surface_happy_path(client: TestClient, db: Session) -> None:
    project = _seed_scored_project(db)
    pid = project.id

    risk = client.get(f"/projects/{pid}/risk")
    assert risk.status_code == 200
    assert len(risk.json()) == 16 * 10          # 16 boreholes x 10 categories

    meta = client.get(f"/projects/{pid}/surface/rise/meta").json()
    assert meta["available"] is True
    assert meta["n_boreholes"] == 16

    png = client.get(f"/projects/{pid}/surface/rise.png")
    assert png.status_code == 200
    assert png.headers["content-type"] == "image/png"
    assert png.content[:8] == b"\x89PNG\r\n\x1a\n"


def test_kmz_requires_category(client: TestClient, db: Session) -> None:
    project = _seed_scored_project(db)
    # Missing ?category= is a client error (422), not a 500.
    assert client.get(f"/projects/{project.id}/export/kmz").status_code == 422
    ok = client.get(f"/projects/{project.id}/export/kmz?category=rise")
    assert ok.status_code == 200
