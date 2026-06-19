# 08 — GIS Architecture

Spatial layer where risk is rendered, explored, and exported. Code: `backend/fah/gis/` +
Leaflet frontend in `frontend/`.

## Coordinate reference systems

- **Input**: UTM Zone 40N — **EPSG:32640** (standard for Dubai), or lon/lat if supplied.
- **Storage & display**: WGS84 — **EPSG:4326**.
- Reprojection via **pyproj** in `gis/geometry.py` on ingest; both source UTM and derived lon/lat
  are stored on `boreholes`.

> **Interpolation is governed by [13 — Spatial Interpolation](13_SPATIAL_INTERPOLATION.md).**
> The output is a **continuous risk surface draped on satellite imagery** (Google Earth / Leaflet),
> not just coloured borehole dots. Read doc 13 — it is core IP and the most error-prone part of the
> system.

## Components

### `geometry.py`
- Reproject EPSG:32640 → EPSG:4326.
- Build point geometries (boreholes) and polygon geometries (domains, surfaces, masks).

### `domains.py`
- Build **hydrostratigraphic domain polygons** + **barrier/fault lines** from the translation
  engine's per-borehole units, optional imported geology layers, and manual delineation.
- Build the **render mask** = data-support hull (convex hull / α-shape of boreholes, buffered by
  variogram range) ∩ site boundary. Anything outside is "insufficient data" — never coloured low.

### `interpolate.py`
- Interpolates **physical drivers** (groundwater elevation/depth, depth-to-cemented-layer,
  Cl/SO₄/TDS, K) — **not** risk scores — onto a grid.
- **Boundary-constrained & anisotropic**: independent interpolation *within each domain*;
  barrier-aware (geodesic) distance where contacts are gradational; variogram range elongated along
  flow direction.
- Tiered by data density (kriging → natural-neighbour/IDW → no-surface), producing a **value grid
  and a variance grid**. Full method in [doc 13](13_SPATIAL_INTERPOLATION.md).

### `surface.py`
- Runs the **risk engine per grid cell** on the interpolated driver surfaces → risk-score grid +
  per-cell evidence + **confidence grid** (from kriging variance).

### `raster.py`
- Colourises the score grid (Green/Yellow/Orange/Red), applies the render mask, fades low-confidence
  cells → GeoTIFF / PNG for draping.

### `layers.py`
- Serves the rasterised surface plus **GeoJSON contour lines** per risk category, and the
  domain/barrier boundary lines. Borehole points carry `score`, `level`, `confidence_pct`,
  `explanation`, `bh_ref` for popups (the full "why").

### `export.py`
- **KMZ** via `simplekml` — a **`GroundOverlay`** raster (the coloured surface, draped on imagery)
  + a folder of borehole placemarks + barrier/domain lines. (Supersedes placemarks-only KMZ.)
- Delegates the per-project **PDF report** to `backend/fah/reports/pdf_report.py`.

## Map output layers (charter)

Toggleable layers, one per:

1. Groundwater Rise Risk
2. Groundwater Mounding Risk
3. Perching Potential
4. Salinity Risk
5. Asset Risk
6. Flood Susceptibility
7. Hydrostratigraphic Barriers

(The risk engine produces 10 categories; the map surfaces the 7 charter layers, with the
remaining attack/dewatering/liability categories available in popups and the PDF report.)

## Colour scheme

| Level | Colour | Hex |
|-------|--------|-----|
| Low | Green | `#2ECC40` |
| Moderate | Yellow | `#FFDC00` |
| High | Orange | `#FF851B` |
| Critical | Red | `#FF4136` |

Same ramp across the web map, KMZ, and PDF report for consistency.

## Frontend (`frontend/static/js/map.js`)

- **Leaflet** base map (**satellite** base preferred, OSM option) centred on the project extent.
- **Risk surface** — semi-transparent raster image overlay (or XYZ tiles) per category, draped on
  imagery; the continuous coloured surface is the primary visual.
- **Layer control** — toggle each risk-category surface + hydrostratigraphic barriers + the
  **confidence layer** + borehole points.
- **Legend** — the Green/Yellow/Orange/Red ramp, plus the "insufficient data" mask style.
- **Borehole popup** — on click: `bh_ref`, level, score, confidence, and the full hydrogeological
  **explanation** with evidence (the charter's "explain why", at the point of interaction).
- Surfaces fetched as raster overlays; contours/boundaries/boreholes as GeoJSON from the API
  (`/projects/{id}/layers/{category}.geojson`).

## Export formats

| Format | Tool | Contents |
|--------|------|----------|
| **KMZ** | simplekml + rasterio | `GroundOverlay` risk surface(s) draped on imagery + borehole placemarks + barrier/domain lines, foldered by risk category; opens in Google Earth |
| **PDF** | reportlab/weasyprint | Per-project forensic report: site summary, borehole table, per-category risk with explanations + confidence, surface map snapshot + confidence map |

Exports are written to `data/exports/`.
