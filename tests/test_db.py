"""Sprint 1 — schema and reference-data seed."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from fah.db.models import Borehole, Layer, LithologyDictionary, Project
from fah.db.seed import seed_lithology_dictionary


def test_project_borehole_layer_cascade(db: Session) -> None:
    project = Project(name="Marina Plot 7", location="Dubai Marina", crs_input="EPSG:32640")
    db.add(project)
    db.flush()

    bh = Borehole(project_id=project.id, bh_ref="BH-01", gwl_depth_m=1.8)
    db.add(bh)
    db.flush()
    db.add(
        Layer(
            borehole_id=bh.id,
            seq=1,
            top_depth_m=0.0,
            bottom_depth_m=2.0,
            raw_description="Brown silty SAND, loose",
            spt_n=8,
        )
    )
    db.commit()

    assert db.scalar(select(func.count(Borehole.id))) == 1
    assert db.scalar(select(func.count(Layer.id))) == 1

    # Deleting the project cascades to boreholes and layers.
    db.delete(project)
    db.commit()
    assert db.scalar(select(func.count(Borehole.id))) == 0
    assert db.scalar(select(func.count(Layer.id))) == 0


def test_seed_lithology_dictionary(db: Session) -> None:
    n = seed_lithology_dictionary(db)
    db.commit()
    assert n > 0

    sabkha = db.get(LithologyDictionary, "sabkha")
    assert sabkha is not None
    assert sabkha.salinity_flag is True  # sabkha is a salinity source

    sandstone = db.get(LithologyDictionary, "sandstone")
    assert sandstone is not None
    assert sandstone.cemented_default is True
    assert sandstone.default_k_v == "low"  # cementation suppresses vertical K

    # Re-seeding is idempotent (upsert by code).
    n2 = seed_lithology_dictionary(db)
    db.commit()
    assert n2 == n
    assert db.scalar(select(func.count(LithologyDictionary.code))) == n
