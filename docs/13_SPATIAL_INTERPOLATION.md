# 13 — Spatial Interpolation & Boundary-Constrained Surfaces (Core IP)

> This document exists because interpolation is the single most error-prone — and most
> forensically dangerous — part of FAH Explorer. Boreholes are sparse, static point samples; the
> product is a *continuous* risk surface draped on satellite imagery (Google Earth / Leaflet). How
> we get from points to surface **must be explicit, defensible, and geology-aware** before any
> code is written.

## The target and the trap

**Target:** a smooth, colour-graded risk surface over real imagery (cf. an acoustic propagation
map), per risk category, Green→Yellow→Orange→Red.

**Trap:** an acoustic map is a *deterministic physics model* (known sources, known propagation,
contours that bend around buildings). FAH is the opposite — *sparse statistical inference* of a
field that is **controlled by geology we only partially observe**. Treating it like a smooth
continuous field with off-the-shelf interpolation produces confident, beautiful, and **wrong**
maps. Three failure modes we explicitly engineer against:

| Failure | Why it's wrong for FAH | Our countermeasure |
|--------|------------------------|--------------------|
| Interpolating the **risk score** | "Halfway between High and Low" is meaningless; risk is non-linear & derived | **Principle 1** — interpolate *drivers*, compute risk per cell |
| **Smearing across boundaries** | GW behaviour is discontinuous across a barrier/fault/facies change | **Principle 2** — domain-constrained + barrier-aware interpolation |
| **Hiding uncertainty** | A green pixel far from any borehole is a guess, not a measurement | **Principle 3** — kriging variance → confidence surface + hard masking |

---

## Principle 1 — Interpolate physical drivers, NOT risk scores

The risk engine ([06](06_RISK_SCORING_FRAMEWORK.md)) runs **per grid cell**, not just per
borehole. We interpolate the *measured/derived physical inputs* — which are genuinely continuous
fields — then evaluate risk on the interpolated surface.

**Driver fields interpolated (each a continuous, physically meaningful quantity):**

| Driver | Source | Notes |
|--------|--------|-------|
| Groundwater depth (m) | `boreholes.gwl_depth_m` | primary driver of most categories |
| Groundwater elevation (mAOD) | derived | often interpolates better than depth (removes topography) — interpolate elevation, then subtract a DEM to get depth |
| Depth to cemented / low-K_v layer (m) | `hydro_units` | perching / rise driver |
| Chloride, sulphate, TDS (mg/L) | `lab_results` | salinity / attack drivers |
| Representative K_h / K_v | `hydro_units` | dewatering / mounding drivers |
| Ground level (DEM) | external DEM or borehole collars | flood / elevation |

Site-context factors (irrigation, TSE use, ponds, tidal influence) are **polygon/zonal overlays**,
not interpolated point fields — they are applied to the grid by spatial join.

**Result:** the continuous appearance of the map comes from continuous *drivers*; the risk class
at each cell is a true engine evaluation with its own evidence list — so a clicked point anywhere
on the surface can still **explain why**.

---

## Principle 2 — Respect the boundaries that are set

"Boundary which is set" has **two distinct meanings**, and both are honoured:

### 2a. Physical hydrogeological boundaries (discontinuities)
Across these, the field is genuinely discontinuous and interpolation must **not** smear:
- **Hydrostratigraphic barriers** — continuous low-K_v units (`hydro_units.unit_type = barrier`).
- **Faults / structural contacts.**
- **Facies / geological unit changes** (e.g., Sabkha edge, caprock pinch-out).
- **Coastline / tidal boundary** (fresh–saline interface).

**Method — domain decomposition (hard boundaries):**
1. Build **hydrostratigraphic domain polygons** (`gis/domains.py`) from: (a) the translation
   engine's per-borehole unit classification correlated between boreholes, (b) optional imported
   geology/fault GIS layers, (c) manual expert delineation in the review UI.
2. **Interpolate each driver independently within each domain.** A barrier between two domains
   therefore produces a **sharp discontinuity**, not a gradient — physically correct and visually
   honest (the contour "snaps" at the barrier, exactly as the acoustic map's contours snap at a
   building).

**Method — barrier-aware distance (soft, where domains are uncertain):**
Where a hard polygon split is too strong (gradational contacts), replace Euclidean distance with
**geodesic / least-cost distance that routes around barriers**. Two boreholes on opposite sides of
a barrier become "far apart," so their cross-weight collapses — without forcing a knife-edge. This
is *non-Euclidean-distance kriging* (a.k.a. kriging-with-barriers).

### 2b. The data / attribution boundary (no silent extrapolation)
We **never** paint risk where we have no evidence or no mandate:
- Compute the **data support boundary** = convex hull (or α-shape) of boreholes, optionally
  buffered by the variogram range; intersect with the **site / parcel boundary** if supplied.
- **Everything outside is masked** → rendered as "Insufficient data" (hatched/grey), **not green**.
  Green means "assessed and low," never "unknown."

---

## Principle 3 — Quantify spatial uncertainty (confidence as a surface)

The charter requires a **confidence score** on every risk output. Spatially, the natural,
defensible measure is the **kriging variance**: it is low at/near boreholes and grows with
distance and sparsity.

- Produce a **confidence surface** per driver/category: `confidence_pct` per cell from kriging
  variance (calibrated so on-borehole ≈ the point confidence from [06](06_RISK_SCORING_FRAMEWORK.md)).
- Render it as a toggleable layer **and** use it to fade/hatch low-confidence areas of the risk
  surface, so the map cannot mislead.
- This directly answers the "static borehole locations" concern: confidence **decays with
  distance from control points**, visibly and honestly.

---

## Principle 4 — Anisotropy along flow

Groundwater and the risk it drives are **anisotropic** — they elongate along flow direction,
paleochannels, and high-K corridors (e.g., utility trenches puncturing the vadose zone). The
variogram is configured with a **longer range along the dominant flow azimuth** than across it, so
surfaces **stretch along flow paths** rather than forming isotropic "bullseyes" around each
borehole. Flow azimuth comes from the groundwater-elevation gradient (interpolated heads) or
expert input.

---

## Method selection — tiered by data density

Kriging needs enough points to fit a variogram. With few boreholes we degrade *gracefully and
honestly* rather than fake precision:

| Boreholes (per domain) | Method | Confidence treatment |
|------------------------|--------|----------------------|
| **≥ ~15–30**, variogram fits | **Ordinary / Universal Kriging** (anisotropic, domain-constrained); KED with geology as drift where available | Kriging variance → confidence surface |
| **~6–15** | **Natural Neighbour** or **anisotropic IDW**, within domains; no variogram | Distance-decay confidence (flat-ish, conservative) |
| **< 6**, or single sparse domain | **No surface.** Show boreholes + data-hull outline only | Explicit "insufficient spatial data" flag |

Method actually used is **recorded per layer** (`engine_version` + interpolation params) for
reproducibility. We never silently upgrade a sparse dataset to a smooth map.

---

## Pipeline

```
1. domains.py     build hydrostratigraphic domain polygons + barrier lines
                  (+ data-support hull ∩ site boundary = render mask)
2. interpolate.py per driver, per domain:
                     fit anisotropic variogram (or pick fallback by N)
                     krige driver onto grid  →  value grid + variance grid
                     (barrier-aware distance where domains are gradational)
3. surface.py     run RISK ENGINE per grid cell on interpolated drivers
                     →  risk-score grid + per-cell evidence + confidence grid
4. raster.py      colourise (Green/Yellow/Orange/Red), apply mask,
                     fade by confidence  →  GeoTIFF / PNG
5. export/layers  Google Earth: KMZ GroundOverlay (raster drape)
                  Leaflet:      image overlay / XYZ tiles + GeoJSON contours
                  Confidence:   separate toggleable layer
```

Boreholes remain on top as clickable points (full per-borehole explanation); the **surface** is
the interpolated, masked, confidence-aware product beneath them.

---

## Output & rendering (matches the visual target)

- **Google Earth / KMZ:** a **`GroundOverlay`** raster (the coloured surface) draped on imagery —
  this is what produces the look in the reference image — plus a folder of borehole placemarks and
  the barrier/domain boundary lines. (Earlier "placemarks only" KMZ is superseded; see
  [08_GIS_ARCHITECTURE.md](08_GIS_ARCHITECTURE.md).)
- **Leaflet:** semi-transparent image overlay (or tiled raster) over a satellite base, with
  optional GeoJSON contour lines, the legend, the confidence layer, and clickable boreholes.

---

## Libraries

| Need | Library |
|------|---------|
| Kriging (ordinary/universal, anisotropy, variance) | `pykrige` |
| Variogram fitting / custom distance / advanced geostats | `gstools`, `scikit-gstat` |
| Natural neighbour / RBF / IDW fallback | `scipy.interpolate`, `numpy` |
| Domains, barriers, hulls, clipping, spatial joins | `geopandas`, `shapely` |
| Raster I/O, masking, GeoTIFF | `rasterio`, `numpy` |
| KMZ GroundOverlay | `simplekml` |

---

## Forensic defensibility checklist

- [ ] Interpolated **drivers**, not risk scores — every cell's risk is a real engine evaluation.
- [ ] **No interpolation across** a barrier/fault/facies boundary (domain-constrained / barrier-aware).
- [ ] **No extrapolation** beyond the data hull ∩ site boundary — masked as "insufficient data."
- [ ] **Confidence surface** published alongside every risk surface; low-confidence areas faded.
- [ ] Interpolation **method, parameters, and variogram recorded** per layer → reproducible.
- [ ] Anisotropy aligned to a stated, justified flow direction.

This is the spatial expression of the FAH thesis: *geology controls behaviour, behaviour controls
risk — so the map must obey geology, and must admit what it does not know.*
