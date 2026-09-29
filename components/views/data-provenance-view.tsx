"use client";

import React from "react";
import { Database, ShieldCheck, AlertTriangle, FileCode } from "lucide-react";

export function DataProvenanceView() {
  const datasets = [
    {
      name: "SCTD 1.0",
      modality: "Side-scan Sonar (Klein SSS)",
      taxonomy: "wreck_debris (ship, aircraft, containers)",
      license: "MIT",
      role: "Benchmark detection & classification baseline",
      status: "REGISTERED",
    },
    {
      name: "SCTD 2.0",
      modality: "Klein 3000 Multi-Beam / SSS",
      taxonomy: "trap_pot (real small traps, seafloor debris)",
      license: "Apache-2.0",
      role: "Small man-made target geometry validation",
      status: "REGISTERED",
    },
    {
      name: "SeabedObjects-KLSG-II",
      modality: "Continental Shelf High-Res SSS",
      taxonomy: "wreck_debris + clean seafloor negatives",
      license: "CC-BY-4.0",
      role: "False-alarm suppression & background modeling",
      status: "REGISTERED",
    },
    {
      name: "AI4Shipwrecks",
      modality: "EdgeTech 4200 / 4125 SSS",
      taxonomy: "wreck_debris (held-out sites 14 & 22)",
      license: "CC-BY-NC-4.0",
      role: "Zero-leakage spatial generalization held-out test",
      status: "HELD-OUT",
    },
    {
      name: "Ghost Pot SSS",
      modality: "Humminbird 998c SI SSS",
      taxonomy: "trap_pot (abandoned crab pots) + clean tiles",
      license: "GPL-3.0",
      role: "Real derelict fishing gear benchmark",
      status: "REGISTERED",
    },
    {
      name: "NOAA / USGS NCEI",
      modality: "Raw XTF Hydrographic Surveys",
      taxonomy: "Raw navigation packets, layback & bathymetry",
      license: "Public Domain",
      role: "Georeferencing, telemetry parsing, error budgets",
      status: "REGISTERED",
    },
  ];

  return (
    <div className="p-6 space-y-5 max-w-full overflow-y-auto h-full">
      {/* Header */}
      <div className="pb-3 border-b border-border">
        <div className="text-[12px] font-mono text-text-muted">DATA PROVENANCE &amp; SCIENTIFIC INTEGRITY AUDIT</div>
        <h1 className="text-[20px] font-semibold text-text mt-0.5">
          Dataset Registry, Licences &amp; Non-Fabrication Policy
        </h1>
      </div>

      {/* Policy Callout */}
      <div className="p-3.5 bg-surface-2 border border-border rounded text-[13px] text-text leading-relaxed">
        <b>Real-Data-First Mandate:</b> Real hydrographic side-scan sonar data is the primary benchmark for all training, testing, and operational deployment. Hybrid injection is secondary to address ghost-net scarcity without fake field labels. Pure simulation is tertiary for controlled stress-testing.
      </div>

      {/* Non-Fabrication Status Boxes */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="panel p-4 space-y-2">
          <div className="section-label">INDIAN FIELD DATA PATHWAY</div>
          <div className="text-[14px] font-bold text-danger font-mono">
            REAL INDIAN FIELD DATA NOT LOADED
          </div>
          <p className="text-[12px] text-text-muted leading-relaxed">
            Strict refusal to fabricate Indian field data. When permitted NIOT/MoES surveys are loaded into <code>data/real/indian/</code>, they become the highest-priority validation benchmark.
          </p>
        </div>

        <div className="panel p-4 space-y-2">
          <div className="section-label">GHOST NET FIELD VALIDATION STATUS</div>
          <div className="text-[14px] font-bold text-accent font-mono">
            PENDING VERIFIED FIELD DATA
          </div>
          <p className="text-[12px] text-text-muted leading-relaxed">
            No public verified real ghost-net SSS dataset exists globally. Crab-pot data is never mislabeled as nets. Model is trained on real seabed + hybrid net injection.
          </p>
        </div>
      </div>

      {/* Registered Datasets Table */}
      <div className="panel overflow-hidden">
        <div className="px-4 py-2.5 bg-surface-2 border-b border-border flex justify-between items-center">
          <span className="section-label">REGISTERED REAL HYDROGRAPHIC BENCHMARKS</span>
          <span className="font-mono text-[12px] text-text-muted">6 Third-Party Archives</span>
        </div>
        <div className="overflow-x-auto">
          <table className="hydro-table">
            <thead>
              <tr>
                <th>Dataset Name</th>
                <th>Sensor &amp; Modality</th>
                <th>Taxonomy Mapping</th>
                <th>Open Licence</th>
                <th>Role in SagarNetra</th>
                <th>Registry Status</th>
              </tr>
            </thead>
            <tbody>
              {datasets.map((d, idx) => (
                <tr key={idx}>
                  <td className="font-bold text-text font-mono text-[12px]">{d.name}</td>
                  <td>{d.modality}</td>
                  <td className="font-mono text-[12px]">{d.taxonomy}</td>
                  <td className="font-mono text-[12px] text-primary">{d.license}</td>
                  <td className="text-text-muted text-[12px]">{d.role}</td>
                  <td>
                    <span
                      className={`inline-flex px-1.5 py-0.5 rounded text-[11px] font-mono ${
                        d.status === "REGISTERED"
                          ? "bg-success/10 text-success border border-success/30"
                          : "bg-primary/10 text-primary border border-primary/30"
                      }`}
                    >
                      {d.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
