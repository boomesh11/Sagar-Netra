"use client";

import React, { useEffect, useRef } from "react";
import L from "leaflet";
import { Detection } from "@/types/survey";

interface LeafletMapProps {
  detections: Detection[];
  selectedPin: string | null;
  onSelectPin: (id: string) => void;
  showHazards: boolean;
  showSuppressed: boolean;
}

const CLASS_COLORS: Record<string, string> = {
  net_debris: "#C2410C",
  wreck: "#7C2D12",
  pipe_cylinder: "#1D4ED8",
  other_manmade: "#0F766E",
  unknown_manmade: "#4B5563",
};

export default function LeafletMap({
  detections,
  selectedPin,
  onSelectPin,
  showHazards,
  showSuppressed,
}: LeafletMapProps) {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);
  const markersLayerRef = useRef<L.LayerGroup | null>(null);

  // Available georeferenced detections
  const validDetections = detections.filter(
    (d) => d.geo.status === "AVAILABLE" && d.geo.lat !== null && d.geo.lon !== null
  );
  const displayed = validDetections.filter((d) => (showSuppressed ? true : !d.suppressed));

  // Initialize Map
  useEffect(() => {
    if (!mapContainerRef.current || mapInstanceRef.current) return;

    // Default center (or center on first target)
    const initialCenter: [number, number] =
      validDetections.length > 0 && validDetections[0].geo.lat !== null && validDetections[0].geo.lon !== null
        ? [validDetections[0].geo.lat, validDetections[0].geo.lon]
        : [17.6868, 83.3541]; // Coastal India reference

    const map = L.map(mapContainerRef.current, {
      center: initialCenter,
      zoom: 15,
      zoomControl: true,
    });

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors | SagarNetra Hydrographic Engine',
      maxZoom: 19,
    }).addTo(map);

    const markersLayer = L.layerGroup().addTo(map);
    markersLayerRef.current = markersLayer;
    mapInstanceRef.current = map;

    return () => {
      map.remove();
      mapInstanceRef.current = null;
    };
  }, []);

  // Update Markers when detections or filters change
  useEffect(() => {
    const map = mapInstanceRef.current;
    const layer = markersLayerRef.current;
    if (!map || !layer) return;

    layer.clearLayers();

    if (!showHazards || displayed.length === 0) return;

    const bounds = L.latLngBounds([]);

    displayed.forEach((det) => {
      const lat = det.geo.lat!;
      const lon = det.geo.lon!;
      const latLng: [number, number] = [lat, lon];
      bounds.extend(latLng);

      const color = det.suppressed ? "#A61B1B" : CLASS_COLORS[det.class] || "#0B3D91";
      const isSelected = selectedPin === det.id;
      const r95 = det.geo.r95M ?? 2.45;

      // Draw uncertainty radius (r95 search radius circle in meters)
      const circle = L.circle(latLng, {
        radius: r95,
        color: color,
        weight: isSelected ? 2 : 1,
        fillColor: det.suppressed ? "#A61B1B" : "#1B6E3A",
        fillOpacity: isSelected ? 0.35 : 0.2,
      }).addTo(layer);

      // Center dot
      const marker = L.circleMarker(latLng, {
        radius: isSelected ? 7 : 5,
        color: "#FFFFFF",
        weight: 2,
        fillColor: color,
        fillOpacity: 1.0,
      }).addTo(layer);

      const popupContent = `
        <div style="font-family: monospace; font-size: 12px; color: #1F2933; min-width: 160px;">
          <div style="font-weight: bold; border-bottom: 1px solid #D0D7DE; padding-bottom: 4px; margin-bottom: 4px;">
            ${det.id} (${det.class.replace("_", " ")})
          </div>
          <div>Status: <b>${det.suppressed ? "SUPPRESSED" : "VERIFIED"}</b></div>
          <div>Confidence: <b>${Math.round(det.confidence)}%</b></div>
          <div>r95: <b>±${r95.toFixed(2)} m</b></div>
          <div>Lat: ${lat.toFixed(6)}°</div>
          <div>Lon: ${lon.toFixed(6)}°</div>
        </div>
      `;

      marker.bindPopup(popupContent);

      marker.on("click", () => {
        onSelectPin(det.id);
      });
      circle.on("click", () => {
        onSelectPin(det.id);
      });
    });

    if (displayed.length > 0 && bounds.isValid()) {
      map.fitBounds(bounds, { padding: [50, 50], maxZoom: 18 });
    }
  }, [displayed, selectedPin, showHazards, onSelectPin]);

  return <div ref={mapContainerRef} className="w-full h-full z-0" />;
}
