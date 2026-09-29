"use client";

import React, { useState } from "react";
import { Layers, SplitSquareVertical, ArrowRightLeft } from "lucide-react";

export function ChangeDetectionView() {
  const [sliderPos, setSliderPos] = useState(50);
  const [scenario, setScenario] = useState("Cyclone Vardah (Chennai Port)");

  return (
    <div className="p-6 space-y-4 max-w-full overflow-y-auto h-full">
      <div className="pb-3 border-b border-border flex justify-between items-center">
        <div>
          <div className="section-label">POST-DISASTER RAPID RECONNAISSANCE</div>
          <h1 className="text-[20px] font-semibold text-text mt-0.5">
            Pre- vs. Post-Cyclone Acoustic Change Detection
          </h1>
        </div>
        <select
          value={scenario}
          onChange={(e) => setScenario(e.target.value)}
          className="px-2.5 py-1.5 border border-border rounded bg-surface text-text text-[13px] font-medium"
        >
          <option value="Cyclone Vardah (Chennai Port)">Scenario: Cyclone Vardah (Chennai Port)</option>
          <option value="Cyclone Michaung (Ennore Shoals)">Scenario: Cyclone Michaung (Ennore Shoals)</option>
        </select>
      </div>

      {/* Split Comparison Viewer */}
      <div className="panel overflow-hidden">
        <div className="px-4 py-2.5 bg-surface-2 border-b border-border flex justify-between items-center text-[12px] font-mono">
          <span className="text-text-muted">BASELINE: 2026-04-10 (Pre-Storm)</span>
          <span className="text-primary font-bold">DRAG SLIDER TO REVEAL POST-STORM CHANGES</span>
          <span className="text-accent">POST-CYCLONE: 2026-09-22</span>
        </div>

        <div className="relative h-80 bg-[#0A111C] select-none overflow-hidden">
          {/* Baseline Image */}
          <div className="absolute inset-0 flex items-center justify-center text-text-muted font-mono text-[13px]">
            [BASELINE PRE-STORM ACOUSTIC SWATH · CLEAN ANCHORAGE SEABED]
          </div>

          {/* Post-Cyclone Swath with Split Mask */}
          <div
            className="absolute inset-y-0 left-0 bg-[#0F1C2E] border-r-2 border-primary flex items-center justify-center overflow-hidden"
            style={{ width: `${sliderPos}%` }}
          >
            <div className="absolute inset-0 flex flex-col items-center justify-center font-mono text-[13px] text-danger">
              <span>[POST-CYCLONE SURVEY · 3 NEW SUNKEN OBSTRUCTIONS DETECTED]</span>
              <span className="text-[11px] text-text-muted mt-1">Delta Intensity ΔI = I_post - I_base &gt; threshold</span>
            </div>
          </div>

          {/* Range Slider for Interaction */}
          <input
            type="range"
            min="0"
            max="100"
            value={sliderPos}
            onChange={(e) => setSliderPos(Number(e.target.value))}
            className="absolute inset-0 opacity-0 cursor-ew-resize w-full h-full"
          />
        </div>
      </div>

      {/* Detected Changes Table */}
      <div className="panel overflow-hidden">
        <div className="px-4 py-2 bg-surface-2 border-b border-border text-[11px] section-label">
          AUTOMATED RECONNAISSANCE OBSTRUCTIONS IDENTIFIED
        </div>
        <table className="hydro-table">
          <thead>
            <tr>
              <th>Anomaly ID</th>
              <th>Change Classification</th>
              <th>Location (WGS84)</th>
              <th className="numeric">Delta Intensity</th>
              <th>Dimensions</th>
              <th>Clearance Priority</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td className="font-mono font-bold text-[12px]">NEW-OBS-01</td>
              <td className="text-danger font-semibold">Newly Deposited Hull Wreck</td>
              <td className="font-mono">13.08412°N, 80.29740°E</td>
              <td className="numeric font-mono">+84.2%</td>
              <td className="font-mono">14.2m × 3.8m × 2.4m</td>
              <td><span className="px-1.5 py-0.5 rounded bg-danger/10 text-danger font-mono text-[11px]">CRITICAL</span></td>
            </tr>
            <tr>
              <td className="font-mono font-bold text-[12px]">NEW-OBS-02</td>
              <td className="text-accent font-semibold">Displaced Heavy Ghost Net</td>
              <td className="font-mono">13.08590°N, 80.29890°E</td>
              <td className="numeric font-mono">+62.8%</td>
              <td className="font-mono">8.5m × 2.1m × 1.1m</td>
              <td><span className="px-1.5 py-0.5 rounded bg-accent/10 text-accent font-mono text-[11px]">HIGH</span></td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}
