"use client";

import React from "react";
import { Grid, AlertCircle, ShieldCheck } from "lucide-react";

export function CoverageGridView() {
  return (
    <div className="p-6 space-y-4 max-w-full overflow-y-auto h-full">
      <div className="pb-3 border-b border-border flex justify-between items-center">
        <div>
          <div className="section-label">ACOUSTIC CLEARANCE ASSESSMENT</div>
          <h1 className="text-[20px] font-semibold text-text mt-0.5">
            Coverage Adequacy &amp; Clearance Grid Map
          </h1>
        </div>
        <div className="text-[12px] font-mono text-text-muted">
          Sector Resolution: 10m × 10m cells
        </div>
      </div>

      {/* Mandatory Operational Safety Notice */}
      <div className="p-3.5 bg-surface-2 border border-border rounded text-[13px] text-text flex items-start gap-2.5">
        <AlertCircle className="w-4 h-4 text-accent shrink-0 mt-0.5" />
        <div>
          <b>Operational Rule:</b> <i>"No candidate detected does not establish absence of debris."</i> Clearance requires satisfying probability of detection thresholds (P_detect &ge; 80%) under acceptable towfish altitude and acoustic grazing angles.
        </div>
      </div>

      {/* 4 Honest Coverage States Legend */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="panel p-3 border-l-4 border-l-[#1D4ED8]">
          <div className="section-label text-[#1D4ED8]">STATE 1: NOT SURVEYED</div>
          <div className="text-[12px] text-text-muted mt-1">Acoustic gap between adjacent survey swaths.</div>
        </div>

        <div className="panel p-3 border-l-4 border-l-[#B45309]">
          <div className="section-label text-[#B45309]">STATE 2: OBSERVATION LIMITED</div>
          <div className="text-[12px] text-text-muted mt-1">High altitude (H &gt; 15m) or telemetry motion corruption.</div>
        </div>

        <div className="panel p-3 border-l-4 border-l-[#1D5FA6]">
          <div className="section-label text-[#1D5FA6]">STATE 3: OBSERVED — NO CANDIDATE</div>
          <div className="text-[12px] text-text-muted mt-1">P_detect &ge; 80%, clear verified seafloor.</div>
        </div>

        <div className="panel p-3 border-l-4 border-l-[#1B6E3A]">
          <div className="section-label text-[#1B6E3A]">STATE 4: CANDIDATE PRESENT</div>
          <div className="text-[12px] text-text-muted mt-1">Confirmed debris candidate with evidence card.</div>
        </div>
      </div>

      {/* Grid Canvas */}
      <div className="panel p-4 flex flex-col items-center justify-center bg-[#0F1722]">
        <div className="text-[12px] font-mono text-[#8FA1B4] mb-2">
          CHENNAI OUTER ANCHORAGE · CLEARANCE EVALUATION MATRIX (100 × 50 CELLS)
        </div>
        <div className="w-full max-w-4xl h-72 border border-border bg-[#0C1523] p-2 flex flex-col justify-between">
          <div className="grid grid-cols-20 gap-1 h-full">
            {Array.from({ length: 100 }).map((_, i) => {
              let bg = "bg-[#1D5FA6]/30"; // Observed no candidate
              if (i === 12 || i === 45 || i === 78) bg = "bg-[#1B6E3A] animate-pulse"; // Candidate
              else if (i % 7 === 0) bg = "bg-[#B45309]/40"; // Observation limited
              else if (i > 85) bg = "bg-[#1D4ED8]/20"; // Not surveyed
              return <div key={i} className={`rounded-sm ${bg} border border-white/5`} />;
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
