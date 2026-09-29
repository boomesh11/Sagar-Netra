"use client";

import React, { useState } from "react";
import { Cpu, RefreshCw } from "lucide-react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
} from "recharts";

export function SyntheticBenchView() {
  const [burial, setBurial] = useState(30);
  const [rangeM, setRangeM] = useState(35);
  const [snrDb, setSnrDb] = useState(18);

  // Generate PoD curve data
  const podData = [];
  for (let r = 0; r <= 60; r += 5) {
    const decay = 1 / (1 + Math.exp((r - (45 - burial * 0.15)) * 0.2));
    podData.push({
      range: r,
      pod: Math.round(decay * 100),
    });
  }

  return (
    <div className="p-6 space-y-4 max-w-full overflow-y-auto h-full">
      <div className="pb-3 border-b border-border flex justify-between items-center">
        <div>
          <div className="section-label">SONARFORGE ENGINEERING BENCH</div>
          <h1 className="text-[20px] font-semibold text-text mt-0.5">
            Parametric Acoustic Stress-Testing &amp; PoD Sweeps
          </h1>
        </div>
        <div className="text-[12px] font-mono text-text-muted">
          Acoustic Physics Simulation Tier
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Controls Panel */}
        <div className="panel p-4 space-y-4">
          <div className="section-label">PARAMETRIC SWEEP CONTROLS</div>

          <div className="space-y-1">
            <div className="flex justify-between text-[12px]">
              <span className="font-medium text-text">Seabed Burial Depth</span>
              <span className="font-mono">{burial}%</span>
            </div>
            <input
              type="range"
              min="0"
              max="90"
              value={burial}
              onChange={(e) => setBurial(Number(e.target.value))}
              className="w-full cursor-pointer accent-primary"
            />
          </div>

          <div className="space-y-1">
            <div className="flex justify-between text-[12px]">
              <span className="font-medium text-text">Slant Range</span>
              <span className="font-mono">{rangeM} m</span>
            </div>
            <input
              type="range"
              min="10"
              max="60"
              value={rangeM}
              onChange={(e) => setRangeM(Number(e.target.value))}
              className="w-full cursor-pointer accent-primary"
            />
          </div>

          <div className="space-y-1">
            <div className="flex justify-between text-[12px]">
              <span className="font-medium text-text">Acoustic SNR</span>
              <span className="font-mono">{snrDb} dB</span>
            </div>
            <input
              type="range"
              min="5"
              max="30"
              value={snrDb}
              onChange={(e) => setSnrDb(Number(e.target.value))}
              className="w-full cursor-pointer accent-primary"
            />
          </div>

          <div className="p-3 bg-surface-2 rounded border border-border text-[11px] font-mono text-text-muted">
            Formula: h = (L_s · H) / (R + L_s). As burial depth increases, acoustic shadow length shrinks proportionally.
          </div>
        </div>

        {/* PoD Curve Chart */}
        <div className="md:col-span-2 panel p-4 flex flex-col justify-between">
          <div className="section-label mb-2">PROBABILITY OF DETECTION (PoD) VS SLANT RANGE</div>
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={podData} margin={{ top: 10, right: 20, left: -20, bottom: 5 }}>
                <XAxis dataKey="range" tick={{ fontSize: 11 }} stroke="#8FA1B4" unit="m" />
                <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} stroke="#8FA1B4" unit="%" />
                <RechartsTooltip contentStyle={{ fontSize: "12px", padding: "4px 8px" }} />
                <Line type="monotone" dataKey="pod" name="PoD" stroke="#0B3D91" strokeWidth={2} dot={{ r: 3 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <div className="text-[11px] font-mono text-text-muted pt-2 border-t border-border flex justify-between">
            <span>80% Clearance Threshold: Satisfied up to 42m range</span>
            <span>Burial Penalty: -{(burial * 0.2).toFixed(1)} dB</span>
          </div>
        </div>
      </div>
    </div>
  );
}
