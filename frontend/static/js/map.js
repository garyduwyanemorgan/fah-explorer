/* FAH Explorer — interactive risk map (Leaflet). */
(function () {
  const projectId = window.FAH.projectId;
  const base = `/projects/${projectId}`;

  const satellite = L.tileLayer(
    "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    { attribution: "Esri World Imagery", maxZoom: 21 }
  );
  const osm = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "© OpenStreetMap", maxZoom: 19,
  });

  const b = window.FAH.bounds;
  const initView = b ? [[b.south, b.west], [b.north, b.east]] : null;
  const map = L.map("map", { layers: [satellite] });
  if (initView) map.fitBounds(initView, { padding: [40, 40] });
  else map.setView([24.45, 54.4], 6);
  L.control.layers({ Satellite: satellite, "Street (OSM)": osm }).addTo(map);

  let surfaceLayer = null;
  let confidenceLayer = null;
  let markerLayer = null;

  const statusEl = document.getElementById("status");
  const categorySel = document.getElementById("category");
  const surfaceChk = document.getElementById("toggle-surface");
  const confidenceChk = document.getElementById("toggle-confidence");
  const kmzLink = document.getElementById("kmz");
  const pdfLink = document.getElementById("pdf");

  function clearLayer(l) { if (l) { map.removeLayer(l); } return null; }

  async function loadCategory(category) {
    surfaceLayer = clearLayer(surfaceLayer);
    confidenceLayer = clearLayer(confidenceLayer);
    markerLayer = clearLayer(markerLayer);
    kmzLink.href = `${base}/export/kmz?category=${category}`;
    pdfLink.href = `${base}/export/pdf?map_category=${category}`;
    statusEl.textContent = "Loading…";

    // 1. Surface overlay (continuous risk field).
    const meta = await fetch(`${base}/surface/${category}/meta`).then((r) => r.json());
    let bounds = null;
    if (meta.available) {
      const b = meta.bounds;
      bounds = [[b.south, b.west], [b.north, b.east]];
      surfaceLayer = L.imageOverlay(`${base}/surface/${category}.png?` + Date.now(), bounds, { opacity: 0.6 });
      confidenceLayer = L.imageOverlay(meta.confidence_url + "?" + Date.now(), bounds, { opacity: 0.7 });
      if (surfaceChk.checked) surfaceLayer.addTo(map);
      if (confidenceChk.checked) confidenceLayer.addTo(map);
      statusEl.textContent = `Surface: ${meta.method}, ${meta.n_boreholes} boreholes. Drivers: ${meta.drivers_available.join(", ")}`;
    } else {
      statusEl.textContent = meta.reason || "No surface available.";
    }

    // 2. Borehole markers with explanations.
    const gj = await fetch(`${base}/layers/${category}.geojson`).then((r) => r.json());
    markerLayer = L.geoJSON(gj, {
      pointToLayer: (f, latlng) =>
        L.circleMarker(latlng, {
          radius: 7, weight: 2, color: "#0f1c24",
          fillColor: f.properties.color || "#777", fillOpacity: 0.95,
        }),
      onEachFeature: (f, layer) => {
        const p = f.properties;
        const expl = (p.explanation || "").replace(/</g, "&lt;");
        layer.bindPopup(
          `<div class="bh-popup"><b>${p.bh_ref}</b> — ${p.level || "n/a"} ` +
          `(score ${p.score ?? "–"}, conf ${p.confidence_pct ?? "–"}%)<pre>${expl}</pre></div>`
        );
      },
    }).addTo(map);

    const fit = markerLayer.getBounds();
    if (fit.isValid()) map.fitBounds(fit.pad(0.3));
    else if (bounds) map.fitBounds(bounds);
  }

  categorySel.addEventListener("change", () => loadCategory(categorySel.value));
  surfaceChk.addEventListener("change", () => {
    if (!surfaceLayer) return;
    surfaceChk.checked ? surfaceLayer.addTo(map) : map.removeLayer(surfaceLayer);
  });
  confidenceChk.addEventListener("change", () => {
    if (!confidenceLayer) return;
    confidenceChk.checked ? confidenceLayer.addTo(map) : map.removeLayer(confidenceLayer);
  });

  loadCategory(categorySel.value);
})();
