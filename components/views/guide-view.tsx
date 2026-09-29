"use client";

import React, { useState } from "react";
import { useAppState } from "@/lib/app-state";
import {
  BookOpen,
  ShieldCheck,
  Activity,
  Layers,
  HelpCircle,
  CheckCircle2,
  FileText,
  Crosshair,
  Compass,
  UploadCloud,
  ChevronRight,
  Terminal,
  ExternalLink,
  Cpu,
  Database,
  Search,
} from "lucide-react";

export function GuideView() {
  const { setActiveTab } = useAppState();
  const [activeSection, setActiveSection] = useState<string>("overview");
  const [searchQuery, setSearchQuery] = useState<string>("");

  const sections = [
    { id: "overview", title: "1. Mission Overview & System Architecture", icon: Compass },
    { id: "modality", title: "2. Sensor Modality QA (SSS vs. Optical RGB)", icon: ShieldCheck },
    { id: "evidence-logic", title: "3. 5-Term Calibrated Evidence Logic", icon: Activity },
    { id: "physics-formula", title: "4. Acoustic Shadow Relief Height Physics", icon: Crosshair },
    { id: "workflow", title: "5. Operator Workflow & Ingestion Wizard", icon: UploadCloud },
    { id: "tools-canvas", title: "6. Waterfall Canvas & Measurement Tools", icon: Layers },
    { id: "export-gis", title: "7. GIS Map, Provenance & Export Formats", icon: FileText },
    { id: "hotkeys", title: "8. Tactical Keyboard Shortcuts", icon: Terminal },
    { id: "troubleshooting", title: "9. Hydrographic FAQ & Troubleshooting", icon: HelpCircle },
  ];

  const filteredSections = sections.filter((s) =>
    s.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
    s.id.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="flex flex-col h-full overflow-hidden bg-bg">
      {/* Top Header Banner */}
      <div className="bg-surface border-b border-border px-6 py-4 flex items-center justify-between shrink-0">
        <div>
          <div className="flex items-center gap-2 text-[11px] font-mono text-text-muted">
            <span>SAGARNETRA</span>
            <span>/</span>
            <span>OPERATIONAL HYDROGRAPHIC MANUAL</span>
            <span>/</span>
            <span className="text-primary font-semibold">NIOT-MOES-PS26057</span>
          </div>
          <h1 className="text-[20px] font-semibold text-text mt-0.5 flex items-center gap-2">
            <BookOpen className="w-5 h-5 text-primary" strokeWidth={1.5} />
            <span>Hydrographic Operator Reference Manual &amp; Technical Guide</span>
          </h1>
        </div>

        {/* Quick Launch & Search */}
        <div className="flex items-center gap-3">
          <div className="relative w-64">
            <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-text-muted" />
            <input
              type="text"
              placeholder="Search guide topics..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-8 pr-3 py-1.5 text-[12px] bg-surface-2 border border-border rounded text-text placeholder:text-text-muted focus:outline-none focus:border-primary font-mono"
            />
          </div>
          <button
            onClick={() => setActiveTab("analysis")}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-primary text-white text-[12px] font-medium rounded hover:bg-primary-hover transition-colors"
          >
            <span>Launch Analysis</span>
            <ChevronRight className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Main Container: Split-pane Layout */}
      <div className="flex flex-1 min-h-0 overflow-hidden">
        {/* Left Sub-nav (Table of Contents) */}
        <div className="w-[280px] bg-surface border-r border-border flex flex-col shrink-0 overflow-y-auto p-3 space-y-1 select-none">
          <div className="section-label px-2 mb-2">MANUAL SECTIONS</div>
          {filteredSections.map((sec) => {
            const Icon = sec.icon;
            const isActive = activeSection === sec.id;
            return (
              <button
                key={sec.id}
                onClick={() => setActiveSection(sec.id)}
                className={`w-full flex items-center gap-2.5 px-3 py-2 rounded text-[12px] text-left transition-colors font-medium ${
                  isActive
                    ? "bg-primary text-white shadow-sm"
                    : "text-text hover:bg-surface-2"
                }`}
              >
                <Icon className="w-4 h-4 shrink-0" strokeWidth={1.5} />
                <span className="truncate">{sec.title}</span>
              </button>
            );
          })}

          <div className="h-px bg-border my-3" />

          {/* Quick Specifications Card */}
          <div className="p-3 bg-surface-2 border border-border rounded text-[11px] font-mono space-y-1.5 text-text-muted">
            <div className="font-semibold text-text">PLATFORM SPECS:</div>
            <div>· Version: SagarNetra 1.0</div>
            <div>· Ministry: MoES / NIOT</div>
            <div>· Problem Statement: 26057</div>
            <div>· Projection: WGS84 UTM 44N</div>
            <div>· Security: 100% Offline Disk</div>
          </div>
        </div>

        {/* Right Content Pane */}
        <div className="flex-1 overflow-y-auto p-6 lg:p-8 space-y-8 max-w-5xl">
          {/* SECTION 1: OVERVIEW */}
          {activeSection === "overview" && (
            <div className="space-y-6">
              <div className="border-b border-border pb-3">
                <span className="section-label">CHAPTER 01</span>
                <h2 className="text-[22px] font-bold text-text">Mission Overview &amp; Architectural Framework</h2>
                <p className="text-[13px] text-text-muted mt-1 leading-relaxed">
                  Operational mandate for automated, physics-grounded detection of marine debris, ghost fishing gear, and submerged navigational hazards in side-scan sonar (SSS) records.
                </p>
              </div>

              {/* Core Philosophy Card */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="p-4 bg-surface border border-border rounded space-y-1.5">
                  <div className="flex items-center gap-2 text-primary font-semibold text-[13px]">
                    <ShieldCheck className="w-4 h-4" />
                    <span>Physics Verification</span>
                  </div>
                  <p className="text-[12px] text-text-muted leading-relaxed">
                    Zero hallucinations. Raw neural proposals are audited against down-range acoustic shadows and towfish beam geometry before validation.
                  </p>
                </div>

                <div className="p-4 bg-surface border border-border rounded space-y-1.5">
                  <div className="flex items-center gap-2 text-primary font-semibold text-[13px]">
                    <Layers className="w-4 h-4" />
                    <span>Multi-Pass Fusion</span>
                  </div>
                  <p className="text-[12px] text-text-muted leading-relaxed">
                    Corroborates hazards across overlapping survey swaths using spatial persistence tracking and WGS84 UTM coordinates.
                  </p>
                </div>

                <div className="p-4 bg-surface border border-border rounded space-y-1.5">
                  <div className="flex items-center gap-2 text-primary font-semibold text-[13px]">
                    <Cpu className="w-4 h-4" />
                    <span>Air-Gapped Operation</span>
                  </div>
                  <p className="text-[12px] text-text-muted leading-relaxed">
                    Designed for survey vessel laboratories. Operates 100% locally on CPU/Edge hardware without internet access or cloud telemetry.
                  </p>
                </div>
              </div>

              {/* Pipeline Diagram */}
              <div className="panel p-5 space-y-3">
                <div className="section-label">END-TO-END HYDROGRAPHIC PIPELINE</div>
                <div className="grid grid-cols-1 sm:grid-cols-5 gap-2 text-center text-[11px] font-mono">
                  <div className="p-3 bg-surface-2 border border-border rounded">
                    <div className="font-bold text-primary">1. INGESTION</div>
                    <div className="text-text-muted mt-1">XTF, JSF, GeoTIFF, PNG, CSV Navigation</div>
                  </div>
                  <div className="p-3 bg-surface-2 border border-border rounded">
                    <div className="font-bold text-primary">2. MODALITY QA</div>
                    <div className="text-text-muted mt-1">1D Acoustic Check &amp; Non-SSS Optical Veto</div>
                  </div>
                  <div className="p-3 bg-surface-2 border border-border rounded">
                    <div className="font-bold text-primary">3. TVG &amp; CFAR</div>
                    <div className="text-text-muted mt-1">Nadir Guarding &amp; Highlight Clustering</div>
                  </div>
                  <div className="p-3 bg-surface-2 border border-border rounded">
                    <div className="font-bold text-primary">4. ECHOSIFT SHC</div>
                    <div className="text-text-muted mt-1">Shadow Geometry &amp; 3D Relief Height H</div>
                  </div>
                  <div className="p-3 bg-surface-2 border border-border rounded">
                    <div className="font-bold text-success">5. CORROBORATION</div>
                    <div className="text-text-muted mt-1">GIS Overlay, GeoJSON &amp; Official Reports</div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* SECTION 2: SENSOR MODALITY */}
          {activeSection === "modality" && (
            <div className="space-y-6">
              <div className="border-b border-border pb-3">
                <span className="section-label">CHAPTER 02</span>
                <h2 className="text-[22px] font-bold text-text">Sensor Modality QA: Side-Scan Sonar vs. Optical RGB</h2>
                <p className="text-[13px] text-text-muted mt-1 leading-relaxed">
                  How SagarNetra mathematically distinguishes single-frequency acoustic intensity records from optical daylight photographs to prevent invalid detections.
                </p>
              </div>

              {/* Technical Comparison Table */}
              <div className="panel overflow-hidden">
                <div className="px-4 py-2 bg-surface-2 border-b border-border font-semibold text-[13px] text-text">
                  Acoustic vs. Optical Chromaticity Profile
                </div>
                <table className="hydro-table">
                  <thead>
                    <tr>
                      <th>Modality</th>
                      <th>Color Representation</th>
                      <th>Mathematical Constraint</th>
                      <th>Status in SagarNetra</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <td className="font-semibold text-text">Monochrome SSS</td>
                      <td>Single-channel grayscale acoustic backscatter</td>
                      <td className="font-mono text-[11px]">|R - G| ≤ 22 &amp; |G - B| ≤ 22</td>
                      <td><span className="badge-verified">Valid SSS (Acoustic Verified)</span></td>
                    </tr>
                    <tr>
                      <td className="font-semibold text-text">Copper / Amber SSS</td>
                      <td>Standard hydrographic false-color (SonarWiz, Klein, EdgeTech)</td>
                      <td className="font-mono text-[11px]">R ≥ G - 8, G ≥ B - 14, B &lt; 0.7R + 25</td>
                      <td><span className="badge-verified">Valid SSS (Copper Colormap)</span></td>
                    </tr>
                    <tr>
                      <td className="font-semibold text-danger">Optical Photograph</td>
                      <td>Natural multi-channel daylight RGB (sky, foliage, cars, people)</td>
                      <td className="font-mono text-[11px]">B &gt; R + 16 or G &gt; R + 20 (Dispersion &gt; 18.0)</td>
                      <td><span className="badge-suppressed">Vetoed (Non-SSS Modality)</span></td>
                    </tr>
                  </tbody>
                </table>
              </div>

              {/* Mathematical Explanation */}
              <div className="p-4 bg-surface-2 border border-border rounded space-y-2 text-[12px] text-text">
                <div className="font-bold font-mono text-primary text-[13px]">
                  Optical Chromatic Violation Formula:
                </div>
                <div className="p-3 bg-surface rounded border border-border font-mono text-[12px]">
                  E_optical = 1.5 · max(0, B - G) + 1.2 · max(0, G - R) + 1.5 · max(0, B - R)
                </div>
                <p className="text-text-muted leading-relaxed">
                  In genuine side-scan sonar, the acoustic backscatter represents pressure amplitude mapped onto a 1-dimensional colormap where Blue is universally attenuated and Green never dominates Red. If an uploaded image exhibits significant Blue or Green dominance (e.g., blue sky, green grass, or multi-hued natural scenes), SagarNetra halts acoustic slant-range models and flags the file with a clear Sensor Modality Audit Veto.
                </p>
              </div>
            </div>
          )}

          {/* SECTION 3: 5-TERM EVIDENCE LOGIC */}
          {activeSection === "evidence-logic" && (
            <div className="space-y-6">
              <div className="border-b border-border pb-3">
                <span className="section-label">CHAPTER 03</span>
                <h2 className="text-[22px] font-bold text-text">5-Term Calibrated Evidence Logic</h2>
                <p className="text-[13px] text-text-muted mt-1 leading-relaxed">
                  Every detected anomaly is evaluated across five independent hydrographic and acoustic metrics to prevent false alarms from natural seabed scouring or biogenic ripples.
                </p>
              </div>

              <div className="space-y-3">
                <div className="p-4 bg-surface border border-border rounded flex gap-4">
                  <div className="w-8 h-8 rounded bg-primary/10 text-primary font-bold font-mono flex items-center justify-center shrink-0">
                    1
                  </div>
                  <div className="space-y-1">
                    <div className="font-semibold text-text text-[13px]">Neural Proposal Score (z_cnn)</div>
                    <p className="text-[12px] text-text-muted leading-relaxed">
                      Initial probability proposal generated by the lightweight INT8 convolutional network trained on hydrographic debris datasets (AI4Shipwrecks, seabed pipelines, lost fishing gear).
                    </p>
                  </div>
                </div>

                <div className="p-4 bg-surface border border-border rounded flex gap-4">
                  <div className="w-8 h-8 rounded bg-primary/10 text-primary font-bold font-mono flex items-center justify-center shrink-0">
                    2
                  </div>
                  <div className="space-y-1">
                    <div className="font-semibold text-text text-[13px]">Shadow-Highlight Consistency (z_shc)</div>
                    <p className="text-[12px] text-text-muted leading-relaxed">
                      Rigorous geometric verification that a specular highlight is immediately accompanied by a down-range acoustic shadow on the correct side (away from the towfish nadir path).
                    </p>
                  </div>
                </div>

                <div className="p-4 bg-surface border border-border rounded flex gap-4">
                  <div className="w-8 h-8 rounded bg-primary/10 text-primary font-bold font-mono flex items-center justify-center shrink-0">
                    3
                  </div>
                  <div className="space-y-1">
                    <div className="font-semibold text-text text-[13px]">Structural Regularity Metric (z_reg)</div>
                    <p className="text-[12px] text-text-muted leading-relaxed">
                      Evaluates spatial linearity, rectangularity, and boundary gradients. Man-made objects (containers, wrecks, pipes) exhibit sharp rectilinear edges, unlike diffuse organic textures.
                    </p>
                  </div>
                </div>

                <div className="p-4 bg-surface border border-border rounded flex gap-4">
                  <div className="w-8 h-8 rounded bg-primary/10 text-primary font-bold font-mono flex items-center justify-center shrink-0">
                    4
                  </div>
                  <div className="space-y-1">
                    <div className="font-semibold text-text text-[13px]">Motion-Artifact Penalty (p_motion)</div>
                    <p className="text-[12px] text-text-muted leading-relaxed">
                      Dynamic penalty deducted when vehicle telemetry records roll/pitch angular rates exceeding ±5° or severe ping cross-correlation drops (&rho; &lt; 0.60) caused by propeller cavitation.
                    </p>
                  </div>
                </div>

                <div className="p-4 bg-surface border border-border rounded flex gap-4">
                  <div className="w-8 h-8 rounded bg-primary/10 text-primary font-bold font-mono flex items-center justify-center shrink-0">
                    5
                  </div>
                  <div className="space-y-1">
                    <div className="font-semibold text-text text-[13px]">Multi-Pass Spatial Persistence (z_persistence)</div>
                    <p className="text-[12px] text-text-muted leading-relaxed">
                      Validates whether the same physical feature appears in adjacent survey tracklines within the 95% navigation error circle (R95 &le; 3.5m). Confirmed multi-pass targets receive priority clearance.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* SECTION 4: ACOUSTIC RELIEF HEIGHT */}
          {activeSection === "physics-formula" && (
            <div className="space-y-6">
              <div className="border-b border-border pb-3">
                <span className="section-label">CHAPTER 04</span>
                <h2 className="text-[22px] font-bold text-text">Acoustic Shadow Relief Height Physics</h2>
                <p className="text-[13px] text-text-muted mt-1 leading-relaxed">
                  How target elevation above the seabed is calculated from the geometry of the acoustic shadow cast across the ocean floor.
                </p>
              </div>

              {/* Formula Card */}
              <div className="p-5 bg-surface border-2 border-primary/30 rounded space-y-3">
                <div className="section-label text-primary">PRIMARY ACOUSTIC ELEVATION FORMULA</div>
                <div className="p-4 bg-surface-2 rounded font-mono text-center text-[16px] font-bold text-text border border-border">
                  H = (A · L_s) / (R_s + L_s)
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-[12px] font-mono">
                  <div className="p-2 bg-surface rounded border border-border">
                    <b>H:</b> Target relief height (m)
                  </div>
                  <div className="p-2 bg-surface rounded border border-border">
                    <b>A:</b> Towfish altitude above seabed (m)
                  </div>
                  <div className="p-2 bg-surface rounded border border-border">
                    <b>L_s:</b> Shadow length down-range (m)
                  </div>
                </div>
                <p className="text-[12px] text-text-muted leading-relaxed">
                  Where <b>R_s</b> is the slant-range distance from the towfish transducer to the contact point of the target highlight.
                </p>
              </div>

              {/* Target Classification Thresholds */}
              <div className="panel overflow-hidden">
                <div className="px-4 py-2 bg-surface-2 border-b border-border font-semibold text-[13px] text-text">
                  Physics Classification Thresholds
                </div>
                <table className="hydro-table">
                  <thead>
                    <tr>
                      <th>Debris Class</th>
                      <th>Relief Height (H)</th>
                      <th>Aspect Ratio</th>
                      <th>Typical Morphological Description</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <td className="font-semibold text-text">Wreck Debris</td>
                      <td className="font-mono">&gt; 1.5m</td>
                      <td className="font-mono">1.2 – 3.5</td>
                      <td>High relief metal hull, structural ribs, massive rectangular shadow.</td>
                    </tr>
                    <tr>
                      <td className="font-semibold text-text">Pipe / Cylinder</td>
                      <td className="font-mono">0.3m – 1.8m</td>
                      <td className="font-mono">&gt; 3.0</td>
                      <td>Linear elongated highlight with continuous parallel shadow.</td>
                    </tr>
                    <tr>
                      <td className="font-semibold text-text">Ghost Net / Entangled Gear</td>
                      <td className="font-mono">0.4m – 1.8m</td>
                      <td className="font-mono">Diffuse</td>
                      <td>Torn synthetic trawl webbing draped over boulders or sediment.</td>
                    </tr>
                    <tr>
                      <td className="font-semibold text-text">Trap / Crab Pot</td>
                      <td className="font-mono">0.2m – 0.9m</td>
                      <td className="font-mono">Square / Round</td>
                      <td>Compact localized obstacle with sharp down-range shadow.</td>
                    </tr>
                    <tr>
                      <td className="font-semibold text-text-muted">Flat Sediment / Ripple</td>
                      <td className="font-mono">&lt; 0.25m</td>
                      <td className="font-mono">N/A</td>
                      <td><b>Auto-Suppressed:</b> Natural sand waves or biological scouring without hazard relief.</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* SECTION 5: WORKFLOW */}
          {activeSection === "workflow" && (
            <div className="space-y-6">
              <div className="border-b border-border pb-3">
                <span className="section-label">CHAPTER 05</span>
                <h2 className="text-[22px] font-bold text-text">Operator Workflow &amp; Survey Ingestion</h2>
                <p className="text-[13px] text-text-muted mt-1 leading-relaxed">
                  Step-by-step procedures for ingesting raw hydrographic surveys, setting acquisition parameters, and launching inference.
                </p>
              </div>

              <div className="space-y-4 text-[13px] text-text">
                <div className="p-4 bg-surface border border-border rounded space-y-2">
                  <div className="font-bold text-primary flex items-center gap-2">
                    <span className="px-2 py-0.5 bg-primary/10 rounded font-mono text-[11px]">STEP 01</span>
                    <span>Upload Sonar Records</span>
                  </div>
                  <p className="text-text-muted text-[12px] leading-relaxed">
                    Navigate to <b>Surveys</b> and click <b>New survey upload</b>. Drag and drop native sonar logs (.xtf, .jsf), hydrographic rasters (.tif, .png, .jpg), and navigation telemetry CSV. The modality engine will automatically perform real-time acoustic validation.
                  </p>
                </div>

                <div className="p-4 bg-surface border border-border rounded space-y-2">
                  <div className="font-bold text-primary flex items-center gap-2">
                    <span className="px-2 py-0.5 bg-primary/10 rounded font-mono text-[11px]">STEP 02</span>
                    <span>Set Acquisition Parameters</span>
                  </div>
                  <p className="text-text-muted text-[12px] leading-relaxed">
                    Verify survey vessel platform (e.g., ORV Sagar Nidhi), sonar frequency (100–900 kHz), nominal range scale (50–150m), and average towfish altitude (8–15m). These values calibrate the physical slant-range and height calculations.
                  </p>
                </div>

                <div className="p-4 bg-surface border border-border rounded space-y-2">
                  <div className="font-bold text-primary flex items-center gap-2">
                    <span className="px-2 py-0.5 bg-primary/10 rounded font-mono text-[11px]">STEP 03</span>
                    <span>Execute Inference Pipeline</span>
                  </div>
                  <p className="text-text-muted text-[12px] leading-relaxed">
                    Click <b>Run Detection Pipeline</b>. The system processes the image across baseline TVG smoothing, nadir water column exclusion, CFAR highlight clustering, and EchoSift down-range shadow search.
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* SECTION 6: TOOLS & CANVAS */}
          {activeSection === "tools-canvas" && (
            <div className="space-y-6">
              <div className="border-b border-border pb-3">
                <span className="section-label">CHAPTER 06</span>
                <h2 className="text-[22px] font-bold text-text">Waterfall Canvas &amp; Hydrographic Measurement Tools</h2>
                <p className="text-[13px] text-text-muted mt-1 leading-relaxed">
                  How to utilize the analysis viewport, measurement calipers, range ruler, and display layers.
                </p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-[12px]">
                <div className="p-4 bg-surface border border-border rounded space-y-2">
                  <div className="font-semibold text-text flex items-center gap-2">
                    <Crosshair className="w-4 h-4 text-primary" />
                    <span>Pan &amp; Zoom Tools</span>
                  </div>
                  <p className="text-text-muted leading-relaxed">
                    Use mouse wheel to zoom (0.6x to 3.5x). Select the Pan tool or hold <code>Space</code> to drag across long waterfall records. Click the Reset button to return to 1.0x native aspect.
                  </p>
                </div>

                <div className="p-4 bg-surface border border-border rounded space-y-2">
                  <div className="font-semibold text-text flex items-center gap-2">
                    <Layers className="w-4 h-4 text-primary" />
                    <span>Measure Caliper Tool</span>
                  </div>
                  <p className="text-text-muted leading-relaxed">
                    Click the Ruler icon or press <code>M</code>. Click and drag between any two points on the seabed to measure ground distance in meters calibrated against the survey range scale.
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* SECTION 7: EXPORT & GIS */}
          {activeSection === "export-gis" && (
            <div className="space-y-6">
              <div className="border-b border-border pb-3">
                <span className="section-label">CHAPTER 07</span>
                <h2 className="text-[22px] font-bold text-text">GIS Map, Provenance &amp; Export Formats</h2>
                <p className="text-[13px] text-text-muted mt-1 leading-relaxed">
                  Standards-compliant hydrographic data exports for integration with QGIS, ArcGIS, Hypack, SonarWiz, and government portals.
                </p>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-[12px]">
                <div className="p-4 bg-surface border border-border rounded space-y-1.5">
                  <div className="font-bold text-text font-mono">GeoJSON Hazard Layer (.geojson)</div>
                  <p className="text-text-muted leading-relaxed">
                    Standard OGC FeatureCollection with point geometries, calibrated confidence, target relief heights, and suppression metadata. Ready for QGIS and Bhuvan portals.
                  </p>
                </div>

                <div className="p-4 bg-surface border border-border rounded space-y-1.5">
                  <div className="font-bold text-text font-mono">Hydrographic CSV Manifest (.csv)</div>
                  <p className="text-text-muted leading-relaxed">
                    Tabular manifest containing Target ID, classification, relief height (m), latitude, longitude, horizontal precision (R95), and validation status.
                  </p>
                </div>

                <div className="p-4 bg-surface border border-border rounded space-y-1.5">
                  <div className="font-bold text-text font-mono">Google Earth KML (.kml)</div>
                  <p className="text-text-muted leading-relaxed">
                    Keyhole Markup Language export with color-coded placemarks for verified hazards and survey line tracks.
                  </p>
                </div>

                <div className="p-4 bg-surface border border-border rounded space-y-1.5">
                  <div className="font-bold text-text font-mono">Audit JSON Dossier (.json)</div>
                  <p className="text-text-muted leading-relaxed">
                    Complete cryptographic audit trail including acquisition parameters, SHA-256 data hashes, TVG coefficients, and full evidence scores.
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* SECTION 8: HOTKEYS */}
          {activeSection === "hotkeys" && (
            <div className="space-y-6">
              <div className="border-b border-border pb-3">
                <span className="section-label">CHAPTER 08</span>
                <h2 className="text-[22px] font-bold text-text">Tactical Keyboard Shortcuts</h2>
                <p className="text-[13px] text-text-muted mt-1 leading-relaxed">
                  Accelerate operational survey review during offshore operations using keyboard shortcuts.
                </p>
              </div>

              <div className="panel overflow-hidden">
                <table className="hydro-table font-mono text-[12px]">
                  <thead>
                    <tr>
                      <th className="w-32">Key</th>
                      <th>Action</th>
                      <th>Scope</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <td><kbd className="px-2 py-0.5 bg-surface-2 border border-border rounded text-text font-bold">1</kbd></td>
                      <td>Navigate to Surveys / Repository view</td>
                      <td>Global</td>
                    </tr>
                    <tr>
                      <td><kbd className="px-2 py-0.5 bg-surface-2 border border-border rounded text-text font-bold">2</kbd></td>
                      <td>Navigate to Analysis / Waterfall view</td>
                      <td>Global</td>
                    </tr>
                    <tr>
                      <td><kbd className="px-2 py-0.5 bg-surface-2 border border-border rounded text-text font-bold">3</kbd></td>
                      <td>Navigate to GIS Map view</td>
                      <td>Global</td>
                    </tr>
                    <tr>
                      <td><kbd className="px-2 py-0.5 bg-surface-2 border border-border rounded text-text font-bold">4</kbd></td>
                      <td>Navigate to Reports &amp; Export view</td>
                      <td>Global</td>
                    </tr>
                    <tr>
                      <td><kbd className="px-2 py-0.5 bg-surface-2 border border-border rounded text-text font-bold">P</kbd></td>
                      <td>Toggle Physics-Verification filter on/off</td>
                      <td>Analysis View</td>
                    </tr>
                    <tr>
                      <td><kbd className="px-2 py-0.5 bg-surface-2 border border-border rounded text-text font-bold">M</kbd></td>
                      <td>Activate Measure caliper tool</td>
                      <td>Analysis Canvas</td>
                    </tr>
                    <tr>
                      <td><kbd className="px-2 py-0.5 bg-surface-2 border border-border rounded text-text font-bold">Space</kbd></td>
                      <td>Hold to Pan across sonar waterfall</td>
                      <td>Analysis Canvas</td>
                    </tr>
                    <tr>
                      <td><kbd className="px-2 py-0.5 bg-surface-2 border border-border rounded text-text font-bold">Esc</kbd></td>
                      <td>Close active dialog or reset selection</td>
                      <td>Modals &amp; Views</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* SECTION 9: TROUBLESHOOTING */}
          {activeSection === "troubleshooting" && (
            <div className="space-y-6">
              <div className="border-b border-border pb-3">
                <span className="section-label">CHAPTER 09</span>
                <h2 className="text-[22px] font-bold text-text">Hydrographic FAQ &amp; Troubleshooting</h2>
                <p className="text-[13px] text-text-muted mt-1 leading-relaxed">
                  Answers to operational questions and diagnostics for common survey processing anomalies.
                </p>
              </div>

              <div className="space-y-4 text-[13px]">
                <div className="p-4 bg-surface border border-border rounded space-y-1.5">
                  <div className="font-bold text-text">Q: Why did my image trigger the "Non-SSS Optical Image" veto?</div>
                  <p className="text-text-muted text-[12px] leading-relaxed">
                    SagarNetra checks whether the image conforms to 1D acoustic intensity (monochrome or copper/amber colormaps). If an image has high Blue or Green dominance (e.g. photos of blue skies, surface water, foliage, people, cars, or colorful charts), the system prevents invalid acoustic processing. Real side-scan sonar images rendered in copper, amber, sepia, or grayscale will pass with 95%+ confidence.
                  </p>
                </div>

                <div className="p-4 bg-surface border border-border rounded space-y-1.5">
                  <div className="font-bold text-text">Q: Why are targets marked with "Georeference: UNAVAILABLE"?</div>
                  <p className="text-text-muted text-[12px] leading-relaxed">
                    By strict NIOT hydrographic policy, if a sonar raster is uploaded without an accompanying navigation telemetry log (.csv) or embedded XTF/JSF ping coordinates, coordinates are reported as <code>UNAVAILABLE</code>. The system never fabricates or guesses geographic coordinates.
                  </p>
                </div>

                <div className="p-4 bg-surface border border-border rounded space-y-1.5">
                  <div className="font-bold text-text">Q: Why was an obvious seabed highlight marked as suppressed?</div>
                  <p className="text-text-muted text-[12px] leading-relaxed">
                    Under the EchoSift physics filter, an acoustic highlight without a corresponding down-range acoustic shadow has a calculated height of 0.0m. This indicates a flat sediment patch (such as gravel or shell hash) rather than an elevated debris hazard. You can view all candidates by switching to <b>Raw Detector Output</b> in the top toolbar.
                  </p>
                </div>

                <div className="p-4 bg-surface border border-border rounded space-y-1.5">
                  <div className="font-bold text-text">Q: Does SagarNetra transmit survey data over the internet?</div>
                  <p className="text-text-muted text-[12px] leading-relaxed">
                    No. SagarNetra is architected for strict offline, air-gapped survey deployments. All neural inference, TVG filtering, and shadow geometry calculations run client-side on local hardware. Zero telemetry or sonar data is transmitted externally.
                  </p>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
