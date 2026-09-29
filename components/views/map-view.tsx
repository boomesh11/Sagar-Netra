"use client";

import React, { useState } from "react";
import dynamic from "next/dynamic";
import { useAppState } from "@/lib/app-state";
import { Navigation, Eye, CheckCircle2, AlertOctagon, ShieldAlert, MapPinOff } from "lucide-react";

// Dynamically import Leaflet map component (SSR disabled for browser window access)
const LeafletMap = dynamic(() => import("@/components/leaflet-map"), {
  ssr: false,
  loading: () => (
    <div className="w-full h-full flex items-center justify-center bg-surface-2 text-text-muted text-[13px] font-mono">
      Initializing Geodetic Tile Layer...
    </div>
  ),
});

export function MapView() {
  const { currentSurvey, detections, setSelectedDetection, setActiveTab } = useAppState();

  const [showTrack, setShowTrack] = useState(true);
  const [showSwath, setShowSwath] = useState(true);
  const [showHazards, setShowHazards] = useState(true);
  const [showSuppressed, setShowSuppressed] = useState(false);
  const [selectedPin, setSelectedPin] = useState<string | null>(null);

  const isGeoAvailable = currentSurvey.geoStatus === "AVAILABLE";
  const validDetections = detections.filter(
    (d) => d.geo.status === "AVAILABLE" && d.geo.lat !== null && d.geo.lon !== null
  );

  const activeDet = detections.find((d) => d.id === selectedPin) || validDetections[0] || detections[0];

  return (
    <div className="flex flex-col h-full overflow-hidden bg-bg p-4 space-y-3">
      {/* Top Header & Layer Toggles Bar */}
      <div className="bg-surface border border-border rounded px-4 py-2.5 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 shrink-0">
        <div>
          <div className="section-label">GEODETIC CHARTING ENGINE</div>
          <div className="text-[16px] font-semibold text-text flex items-center gap-2 flex-wrap">
            <span>{currentSurvey.name}</span>
            {(currentSurvey.isDemoSynthetic || currentSurvey.name.includes("DEMO")) && (
              <span className="px-2 py-0.5 rounded text-[11px] font-mono bg-amber-500/10 text-amber-500 border border-amber-500/30 font-semibold">
                DEMO — SYNTHETIC DATA
              </span>
            )}
          </div>
        </div>

        {/* Layer Toggles */}
        {isGeoAvailable && (
          <div className="flex items-center gap-4 text-[12px]">
            <span className="section-label hidden sm:inline">CHART LAYERS:</span>
            <label className="flex items-center gap-1.5 cursor-pointer text-text">
              <input
                type="checkbox"
                checked={showHazards}
                onChange={(e) => setShowHazards(e.target.checked)}
                className="accent-primary"
              />
              <span>Verified Hazards</span>
            </label>
            <label className="flex items-center gap-1.5 cursor-pointer text-text">
              <input
                type="checkbox"
                checked={showSuppressed}
                onChange={(e) => setShowSuppressed(e.target.checked)}
                className="accent-primary"
              />
              <span>Suppressed Artifacts</span>
            </label>
          </div>
        )}
      </div>

      {/* Main Map Viewport & Detail Sidebar */}
      <div className="flex-1 flex flex-col lg:flex-row gap-3 min-h-0">
        {/* Map Canvas / Leaflet or Unavailable Notice */}
        <div className="flex-1 panel bg-[#0C1523] border border-border relative overflow-hidden flex flex-col min-h-[350px]">
          {isGeoAvailable && validDetections.length > 0 ? (
            <LeafletMap
              detections={detections}
              selectedPin={selectedPin || (validDetections[0]?.id ?? null)}
              onSelectPin={(id) => {
                setSelectedPin(id);
                const d = detections.find((item) => item.id === id);
                if (d) setSelectedDetection(d);
              }}
              showHazards={showHazards}
              showSuppressed={showSuppressed}
            />
          ) : (
            <div className="w-full h-full flex flex-col items-center justify-center p-8 text-center bg-surface/50">
              <div className="w-14 h-14 rounded-full bg-border/40 flex items-center justify-center mb-4">
                <MapPinOff className="w-7 h-7 text-text-muted" />
              </div>
              <h3 className="text-[16px] font-semibold text-text mb-2">
                Geodetic Charting Unavailable (Image-only input without navigation metadata)
              </h3>
              <p className="text-[13px] text-text-muted max-w-lg mb-4">
                This survey was ingested as a standalone raster image without an accompanying navigation telemetry log (.csv) or embedded XTF georeferencing pings.
                Acoustic pixel coordinates (row, col) cannot be projected onto WGS84 coordinates without vessel trajectory data.
              </p>
              <div className="p-3 bg-surface-2 border border-border rounded text-[12px] font-mono text-left max-w-md">
                <div className="font-semibold text-text mb-1">To enable geodetic charting:</div>
                <div className="text-text-muted">1. Re-upload survey with a matching navigation CSV (time, lat, lon, heading, altitude).</div>
                <div className="text-text-muted">2. Or ingest native EdgeTech JSF / Klein XTF files with embedded navigation packets.</div>
              </div>
            </div>
          )}
        </div>

        {/* Right Detail Card for Selected Pin */}
        <div className="w-full lg:w-[340px] panel bg-surface border border-border p-4 flex flex-col justify-between shrink-0 select-none">
          {activeDet ? (
            <div className="space-y-4">
              <div className="pb-2 border-b border-border">
                <div className="section-label">GEOREFERENCED TARGET RECORD</div>
                <div className="text-[18px] font-bold text-text font-mono mt-0.5">{activeDet.id}</div>
                <div className="text-[12px] text-text-muted capitalize">
                  Classification: <b>{activeDet.class.replace("_", " ")}</b>
                </div>
              </div>

              <div className="space-y-2 text-[12px] font-mono bg-surface-2 p-3 rounded border border-border">
                <div className="flex justify-between">
                  <span className="text-text-muted">POSITION STATUS:</span>
                  <span className={`font-semibold ${activeDet.geo.status === "AVAILABLE" ? "text-success" : "text-text-muted"}`}>
                    {activeDet.geo.status}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-text-muted">LATITUDE:</span>
                  <span className="text-text font-semibold">
                    {activeDet.geo.lat !== null ? `${activeDet.geo.lat.toFixed(6)}°N` : "UNAVAILABLE"}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-text-muted">LONGITUDE:</span>
                  <span className="text-text font-semibold">
                    {activeDet.geo.lon !== null ? `${activeDet.geo.lon.toFixed(6)}°E` : "UNAVAILABLE"}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-text-muted">UNCERTAINTY r95:</span>
                  <span className="text-text font-semibold">
                    {activeDet.geo.r95M != null ? `±${activeDet.geo.r95M.toFixed(2)} m` : "UNAVAILABLE"}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-text-muted">SEARCH BOX (2xr95):</span>
                  <span className="text-text font-semibold">
                    {activeDet.geo.r95M != null
                      ? `${(activeDet.geo.r95M * 2).toFixed(1)}m × ${(activeDet.geo.r95M * 2).toFixed(1)}m`
                      : "UNAVAILABLE"}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-text-muted">ESTIMATED HEIGHT:</span>
                  <span className="text-text font-semibold">{activeDet.heightEstimateM ?? 0.0} m</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-text-muted">CONFIDENCE:</span>
                  <span className={`font-bold ${activeDet.suppressed ? "text-danger" : "text-success"}`}>
                    {Math.round(activeDet.confidence)}%
                  </span>
                </div>
              </div>

              {activeDet.suppressed ? (
                <div className="p-2.5 bg-danger/10 border border-danger/30 rounded text-[12px] text-danger">
                  <b>SUPPRESSED:</b> {activeDet.suppressionReason || "Acoustic physics veto"}
                </div>
              ) : (
                <div className="p-2.5 bg-success/10 border border-success/30 rounded text-[12px] text-success">
                  <b>VERIFIED HAZARD:</b> Ready for clearance manifest export.
                </div>
              )}

              <button
                onClick={() => setActiveTab("analysis")}
                className="w-full py-2 bg-primary hover:bg-primary-hover text-white text-[13px] font-medium rounded transition-colors"
              >
                Inspect in Waterfall Canvas
              </button>
            </div>
          ) : (
            <div className="text-[13px] text-text-muted text-center py-8">
              No target selected. Ingest a survey to inspect detections.
            </div>
          )}

          <div className="text-[11px] font-mono text-text-muted pt-2 border-t border-border">
            Hydrographic projection: WGS84 / UTM. Slant-range corrected.
          </div>
        </div>
      </div>
    </div>
  );
}
