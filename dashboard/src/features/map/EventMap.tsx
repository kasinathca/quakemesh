import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { useEffect, useRef, useState } from "react";

import type { EventRecord } from "../../types/contracts";

export function EventMap({ event }: { event: EventRecord | null }) {
  const element = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map | null>(null);
  const layer = useRef<L.LayerGroup | null>(null);
  const [tilesUnavailable, setTilesUnavailable] = useState(false);

  useEffect(() => {
    if (!element.current || map.current) return;
    map.current = L.map(element.current, { zoomControl: true }).setView([12.9716, 77.5946], 11);
    const tiles = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: "© OpenStreetMap contributors",
    });
    tiles.on("tileerror", () => setTilesUnavailable(true));
    tiles.addTo(map.current);
    layer.current = L.layerGroup().addTo(map.current);
    const currentMap = map.current;
    return () => {
      currentMap.remove();
      map.current = null;
    };
  }, []);

  useEffect(() => {
    if (!map.current || !layer.current) return;
    layer.current.clearLayers();
    if (!event) return;
    const points: L.LatLngExpression[] = [];
    for (const polygon of event.frontier_polygons) {
      const boundary = polygon.boundary.map(([latitude, longitude]) => [latitude, longitude] as [number, number]);
      L.polygon(boundary, { color: "#b26a00", weight: 1, dashArray: "5 4", fillOpacity: 0.08 }).addTo(layer.current);
      points.push(...boundary);
    }
    for (const polygon of event.footprint_polygons) {
      const boundary = polygon.boundary.map(([latitude, longitude]) => [latitude, longitude] as [number, number]);
      L.polygon(boundary, { color: "#315da8", weight: 2, fillOpacity: 0.28 }).addTo(layer.current);
      points.push(...boundary);
    }
    if (points.length) map.current.fitBounds(L.latLngBounds(points), { padding: [24, 24], maxZoom: 14 });
  }, [event]);

  return (
    <div className="map-frame">
      <div ref={element} className="map-canvas" aria-label="Event footprint map" />
      {tilesUnavailable ? (
        <div className="map-notice">Map tiles unavailable. Verified footprint geometry remains listed below.</div>
      ) : null}
      {!event ? <div className="map-empty">Waiting for a confirmed event</div> : null}
    </div>
  );
}
