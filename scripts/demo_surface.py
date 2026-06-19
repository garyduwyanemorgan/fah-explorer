"""Demo: build a multi-borehole project, run the full pipeline, emit a risk surface + KMZ.

Usage:  python scripts/demo_surface.py
Writes a PNG and KMZ to data/exports/ and prints the local map URL.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from fah.config import configure_logging, get_settings  # noqa: E402
from fah.db.models import Borehole, LabResult, Layer, Project  # noqa: E402
from fah.db.session import init_db, session_scope  # noqa: E402
from fah.gis import export, render  # noqa: E402
from fah.gis.surface import build_surfaces  # noqa: E402
from fah.risk.engine import assess_project  # noqa: E402
from fah.translate.pipeline import translate_project  # noqa: E402

_E0, _N0 = 500_000.0, 2_700_000.0


def main() -> None:
    configure_logging()
    log = logging.getLogger("fah.scripts.demo_surface")
    init_db()

    with session_scope() as db:
        project = Project(name="Demo Industrial Site", location="Abu Dhabi", crs_input="EPSG:32640")
        db.add(project); db.flush()
        k = 0
        for i in range(4):
            for j in range(3):
                k += 1
                bh = Borehole(
                    project_id=project.id, bh_ref=f"BH-{k:02d}",
                    easting=_E0 + i * 120, northing=_N0 + j * 120,
                    ground_level_m=3.0, gwl_depth_m=1.0 + 0.25 * (i + j),
                )
                db.add(bh); db.flush()
                db.add(Layer(borehole_id=bh.id, seq=1, top_depth_m=0.0, bottom_depth_m=2.0,
                             raw_description="Brown SAND, loose", spt_n=6))
                db.add(Layer(borehole_id=bh.id, seq=2, top_depth_m=2.0, bottom_depth_m=6.0,
                             raw_description="Grey SABKHA, gypsiferous" if (i + j) % 2
                             else "Weakly cemented SANDSTONE", spt_n=None))
                db.add(LabResult(borehole_id=bh.id, depth_m=1.5, parameter="chloride",
                                 value=2500 + 700 * (i + j), unit="mg/L"))
        pid = project.id
        db.flush()

        translate_project(db, pid)
        assess_project(db, pid, site={"irrigated": True, "tse_use": False})

        surfaces = build_surfaces(db, pid)
        exports = get_settings().exports_dir
        exports.mkdir(parents=True, exist_ok=True)
        if surfaces:
            (exports / "demo_rise_surface.png").write_bytes(
                render.score_grid_to_png(surfaces.score_grids["rise"])
            )
            kmz = export.export_kmz(db, pid, "rise", exports, surfaces)
            log.info("Surface method=%s, bounds=%s", surfaces.method, surfaces.bounds)
            log.info("Wrote %s and %s", exports / "demo_rise_surface.png", kmz)
        else:
            log.warning("No surface produced (insufficient boreholes).")

        log.info("Open the map at:  http://127.0.0.1:8000/projects/%d/map", pid)


if __name__ == "__main__":
    main()
