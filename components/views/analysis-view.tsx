"use client";

import React, { useState, useRef, useEffect } from "react";
import { useAppState } from "@/lib/app-state";
import { Detection } from "@/types/survey";
import {
  Hand,
  ZoomIn,
  Ruler,
  SlidersHorizontal,
  CheckCircle,
  XCircle,
  AlertTriangle,
  RotateCcw,
  ShieldCheck,
  Check,
  X,
  Eye,
  Filter,
  Layers,
} from "lucide-react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
  ReferenceArea,
} from "recharts";

export function AnalysisView() {
  const {
    currentSurvey,
    detections,
    selectedDetection,
    setSelectedDetection,
    physicsVerified,
    setPhysicsVerified,
    isProcessing,
    setIsProcessing,
    uploadedImageElement,
    uploadedImageUrl,
  } = useAppState();

  // Tool Strip active tool
  const [activeTool, setActiveTool] = useState<"pan" | "zoom" | "measure">("pan");

  // Overlay toggles
  const [showDetections, setShowDetections] = useState(true);
  const [showShadows, setShowShadows] = useState(false);
  const [showMotionMask, setShowMotionMask] = useState(false);
  const [showSuppressed, setShowSuppressed] = useState(false);
  const [showGrid, setShowGrid] = useState(false);
  const [isOverlaysOpen, setIsOverlaysOpen] = useState(false);

  // Right panel tab
  const [rightTab, setRightTab] = useState<"detections" | "evidence" | "log">("detections");

  // Pipeline simulation state
  const [stepIndex, setStepIndex] = useState(0);
  const [pipelineSteps, setPipelineSteps] = useState([
    { id: 1, name: "Parsing", duration: 320, status: "pending", log: "Parsed 1,680 XTF ping frames and bathymetry records" },
    { id: 2, name: "Slant-range correction", duration: 450, status: "pending", log: "Mapped slant travel time to flat ground range (±75.0m)" },
    { id: 3, name: "Intensity normalisation", duration: 280, status: "pending", log: "Beam pattern & TVG curve compensation applied" },
    { id: 4, name: "Despeckle", duration: 510, status: "pending", log: "Enhanced Lee 5x5 speckle filter executed" },
    { id: 5, name: "Motion-artifact mask", duration: 390, status: "pending", log: "Flagged 142 corrupted pings from roll/pitch telemetry > 5°" },
    { id: 6, name: "Detection (YOLOv8n)", duration: 680, status: "pending", log: "Evaluated 640x640 tiles across 1,680 pings; 14 proposals generated" },
    { id: 7, name: "Physics verification (EchoSift)", duration: 420, status: "pending", log: "Shadow consistency (SHC) & GRI verified: 6 confirmed, 8 suppressed" },
    { id: 8, name: "Geotagging & report", duration: 250, status: "pending", log: "Projected UTM 44N coordinates with r95 error budgeting" },
  ]);

  // Telemetry data
  const [telemetryData] = useState<{ ping: number; roll?: number; pitch?: number; altitude?: number; correlation?: number }[]>([]);
  const [hoveredPing, setHoveredPing] = useState<number>(450);

  // Canvas zoom/pan state
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [zoomLevel, setZoomLevel] = useState<number>(1);
  const [panOffset, setPanOffset] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState<{ x: number; y: number }>({ x: 0, y: 0 });

  // 8-step Pipeline execution effect when isProcessing is triggered
  useEffect(() => {
    if (!isProcessing) return;

    let current = 0;
    setStepIndex(0);

    const runNextStep = () => {
      if (current >= pipelineSteps.length) {
        setIsProcessing(false);
        return;
      }

      setPipelineSteps((prev) =>
        prev.map((s, idx) =>
          idx === current ? { ...s, status: "running" } : idx < current ? { ...s, status: "completed" } : s
        )
      );

      const duration = pipelineSteps[current].duration;
      setTimeout(() => {
        setPipelineSteps((prev) =>
          prev.map((s, idx) => (idx === current ? { ...s, status: "completed" } : s))
        );
        current++;
        setStepIndex(current);
        runNextStep();
      }, duration);
    };

    runNextStep();
  }, [isProcessing]);

  // Procedural waterfall canvas rendering
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const width = canvas.width;
    const height = canvas.height;

    ctx.save();
    ctx.clearRect(0, 0, width, height);

    // Apply pan and zoom
    ctx.translate(panOffset.x, panOffset.y);
    ctx.scale(zoomLevel, zoomLevel);

    const center = width / 2;
    const nadirWidth = 40;

    // Check if user has uploaded a real sonar image
    if (uploadedImageElement) {
      // 1. Draw real user-uploaded sonar image fitted to waterfall viewport
      ctx.drawImage(uploadedImageElement, 0, 0, width, height);

      // Nadir track indicator line
      ctx.strokeStyle = "rgba(208, 215, 222, 0.4)";
      ctx.lineWidth = 1;
      ctx.setLineDash([4, 4]);
      ctx.beginPath();
      ctx.moveTo(center, 0);
      ctx.lineTo(center, height);
      ctx.stroke();
      ctx.setLineDash([]);
    } else {
      // 2. Fallback procedural hydrographic waterfall (Port | Nadir | Starboard)
      const imgData = ctx.createImageData(width, height);
      for (let y = 0; y < height; y++) {
        for (let x = 0; x < width; x++) {
          const distFromCenter = Math.abs(x - center);
          let val = 0;

          if (distFromCenter < nadirWidth / 2) {
            // Nadir dark water column
            val = 0.04 + Math.random() * 0.02;
          } else {
            // Acoustic seafloor backscatter (sand ripples)
            const ripple = Math.sin(x * 0.08 + y * 0.02) * 0.05;
            const noise = (Math.random() - 0.5) * 0.08;
            val = Math.max(0.04, 0.28 + ripple + noise);
          }

          // Motion artifact lines around y = 240-255 and 360-375
          if ((y >= 240 && y <= 255) || (y >= 360 && y <= 375)) {
            val = 0.02; // Dropout streak
          }

          // Starboard target highlights
          if (x >= center + 80 && x <= center + 125 && y >= 60 && y <= 95) {
            val = 0.88; // Ghost net highlight
          } else if (x > center + 125 && x <= center + 180 && y >= 60 && y <= 95) {
            val = 0.01; // Acoustic shadow
          }

          // Wreck highlight
          if (x >= center + 140 && x <= center + 210 && y >= 140 && y <= 190) {
            val = 0.94; // Shipwreck highlight
          } else if (x > center + 210 && x <= center + 310 && y >= 140 && y <= 190) {
            val = 0.01; // Large wreck shadow
          }

          // Port sediment patch (no shadow)
          if (x >= center - 160 && x <= center - 110 && y >= 110 && y <= 145) {
            val = 0.09;
          }

          // Convert to scientific grayscale (amber/sepia tint standard in hydrography)
          const p = Math.floor(Math.min(1.0, val) * 255);
          const idx = (y * width + x) * 4;
          imgData.data[idx] = Math.min(255, Math.floor(p * 1.05));     // R
          imgData.data[idx + 1] = Math.min(255, Math.floor(p * 0.88)); // G
          imgData.data[idx + 2] = Math.min(255, Math.floor(p * 0.65)); // B
          imgData.data[idx + 3] = 255;
        }
      }
      ctx.putImageData(imgData, 0, 0);

      // Overlays: Nadir Line
      ctx.strokeStyle = "#D0D7DE";
      ctx.lineWidth = 1;
      ctx.setLineDash([4, 4]);
      ctx.beginPath();
      ctx.moveTo(center, 0);
      ctx.lineTo(center, height);
      ctx.stroke();
      ctx.setLineDash([]);
    }

    // Overlay: Grid
    if (showGrid) {
      ctx.strokeStyle = "rgba(255, 255, 255, 0.15)";
      ctx.lineWidth = 0.5;
      for (let x = 50; x < width; x += 50) {
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, height);
        ctx.stroke();
      }
      for (let y = 50; y < height; y += 50) {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(width, y);
        ctx.stroke();
      }
    }

    // Overlay: Motion Mask (Hatched Red)
    if (showMotionMask) {
      ctx.fillStyle = "rgba(166, 27, 27, 0.25)";
      ctx.fillRect(0, 240, width, 16);
      ctx.fillRect(0, 360, width, 16);

      ctx.strokeStyle = "#A61B1B";
      ctx.lineWidth = 1;
      for (let i = -height; i < width + height; i += 10) {
        ctx.beginPath();
        ctx.moveTo(i, 240);
        ctx.lineTo(i + 16, 256);
        ctx.moveTo(i, 360);
        ctx.lineTo(i + 16, 376);
        ctx.stroke();
      }
    }

    // Overlay: Shadow Regions
    if (showShadows) {
      ctx.strokeStyle = "#1D4ED8";
      ctx.lineWidth = 1.5;
      if (!uploadedImageElement) {
        ctx.strokeRect(center + 125, 60, 55, 35);
        ctx.strokeRect(center + 210, 140, 100, 50);
      }
    }

    // Detections Bounding Boxes
    if (showDetections) {
      const activeList = detections.filter((d) => (physicsVerified ? showSuppressed || !d.suppressed : true));

      const origW = uploadedImageElement ? (uploadedImageElement.naturalWidth || width) : width;
      const origH = uploadedImageElement ? (uploadedImageElement.naturalHeight || 1680) : 1680;
      const scaleX = width / origW;
      const scaleY = height / (uploadedImageElement ? origH : 1680);

      activeList.forEach((det) => {
        // Map ping & range to canvas coordinates with scale factors
        const bx = Math.floor(det.bbox.rangeStartPx * scaleX);
        const by = Math.floor(det.bbox.pingStart * scaleY);
        const bw = Math.max(30, Math.floor((det.bbox.rangeEndPx - det.bbox.rangeStartPx) * scaleX));
        const bh = Math.max(20, Math.floor((det.bbox.pingEnd - det.bbox.pingStart) * scaleY));

        const isSelected = selectedDetection?.id === det.id;

        // Class colors
        const classColors: Record<string, string> = {
          net_debris: "#C2410C",
          wreck: "#7C2D12",
          pipe_cylinder: "#1D4ED8",
          other_manmade: "#0F766E",
          unknown_manmade: "#4B5563",
          ghost_net: "#C2410C",
          wreck_debris: "#7C2D12",
          trap_pot: "#0F766E",
          submerged_bicycle: "#D97706",
        };
        const color = classColors[det.class] || "#4B5563";

        if (det.suppressed) {
          // Strikethrough box for suppressed
          ctx.strokeStyle = "#A61B1B";
          ctx.lineWidth = 1.5;
          ctx.strokeRect(bx, by, bw, bh);

          ctx.beginPath();
          ctx.moveTo(bx, by);
          ctx.lineTo(bx + bw, by + bh);
          ctx.moveTo(bx + bw, by);
          ctx.lineTo(bx, by + bh);
          ctx.stroke();

          ctx.fillStyle = "#A61B1B";
          ctx.font = "10px IBM Plex Mono, monospace";
          ctx.fillText(`✕ ${det.id} (supp)`, bx, by - 4);
        } else {
          // Normal box
          ctx.strokeStyle = isSelected ? "#B45309" : color;
          ctx.lineWidth = isSelected ? 2.5 : 1.5;
          ctx.strokeRect(bx, by, bw, bh);

          // Mono label (e.g. Submerged Bicycle · 95%)
          const displayLabel = det.class === "submerged_bicycle" ? "Bicycle" : det.class;
          ctx.fillStyle = isSelected ? "#B45309" : color;
          ctx.font = "10px IBM Plex Mono, monospace";
          ctx.fillText(`${displayLabel} · ${Math.round(det.confidence)}%`, bx, by - 4);
        }
      });
    }

    ctx.restore();
  }, [
    zoomLevel,
    panOffset,
    showDetections,
    showShadows,
    showMotionMask,
    showSuppressed,
    showGrid,
    detections,
    selectedDetection,
    physicsVerified,
    uploadedImageElement,
  ]);

  const verifiedCount = detections.filter((d) => !d.suppressed).length;
  const suppressedCount = detections.filter((d) => d.suppressed).length;

  const handleCanvasClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const clickX = (e.clientX - rect.left - panOffset.x) / zoomLevel;
    const clickY = (e.clientY - rect.top - panOffset.y) / zoomLevel;

    const origW = uploadedImageElement ? (uploadedImageElement.naturalWidth || canvas.width) : canvas.width;
    const origH = uploadedImageElement ? (uploadedImageElement.naturalHeight || 1680) : 1680;
    const scaleX = canvas.width / origW;
    const scaleY = canvas.height / (uploadedImageElement ? origH : 1680);

    const clicked = detections.find((det) => {
      const bx = det.bbox.rangeStartPx * scaleX;
      const by = det.bbox.pingStart * scaleY;
      const bw = Math.max(30, (det.bbox.rangeEndPx - det.bbox.rangeStartPx) * scaleX);
      const bh = Math.max(20, (det.bbox.pingEnd - det.bbox.pingStart) * scaleY);
      return clickX >= bx && clickX <= bx + bw && clickY >= by && clickY <= by + bh;
    });

    if (clicked) {
      setSelectedDetection(clicked);
      setRightTab("evidence");
    }
  };

  return (
    <div className="flex flex-col h-full overflow-hidden bg-bg">
      {/* 8-step Pipeline execution banner if processing */}
      {isProcessing && (
        <div className="bg-surface border-b border-border p-3 shrink-0 shadow-sm">
          <div className="flex items-center justify-between mb-1.5">
            <span className="section-label">PIPELINE EXECUTION PROGRESS: STEP {stepIndex + 1} OF 8</span>
            <span className="font-mono text-[12px] text-text-muted">
              {Math.round(((stepIndex + 1) / 8) * 100)}%
            </span>
          </div>
          <div className="grid grid-cols-8 gap-1.5">
            {pipelineSteps.map((step, idx) => (
              <div
                key={step.id}
                className={`p-1.5 rounded border text-[11px] font-mono flex items-center justify-between ${
                  step.status === "completed"
                    ? "bg-success/10 border-success/40 text-success"
                    : step.status === "running"
                    ? "bg-primary text-white border-primary animate-pulse"
                    : "bg-surface-2 border-border text-text-muted"
                }`}
              >
                <span className="truncate">{step.id}. {step.name}</span>
                {step.status === "completed" && <Check className="w-3 h-3 shrink-0" />}
              </div>
            ))}
          </div>
          <div className="mt-1.5 text-[12px] font-mono text-text-muted flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-primary animate-ping" />
            <span>{pipelineSteps[stepIndex]?.log || "Finalizing report..."}</span>
          </div>
        </div>
      )}

      {/* Main Analysis Workspace: Tool Strip | Canvas | Right Panel */}
      <div className="flex flex-1 min-h-0">
        {/* Left: 64px Vertical Tool Strip */}
        <div className="w-[64px] bg-surface border-r border-border flex flex-col items-center py-3 gap-2 shrink-0 select-none">
          <button
            onClick={() => setActiveTool("pan")}
            title="Pan Tool (drag canvas)"
            className={`w-10 h-10 rounded flex items-center justify-center border transition-colors ${
              activeTool === "pan" ? "bg-primary text-white border-primary" : "text-text-muted hover:bg-surface-2 border-border"
            }`}
          >
            <Hand className="w-4 h-4" strokeWidth={1.5} />
          </button>

          <button
            onClick={() => setActiveTool("zoom")}
            title="Zoom Tool"
            className={`w-10 h-10 rounded flex items-center justify-center border transition-colors ${
              activeTool === "zoom" ? "bg-primary text-white border-primary" : "text-text-muted hover:bg-surface-2 border-border"
            }`}
          >
            <ZoomIn className="w-4 h-4" strokeWidth={1.5} />
          </button>

          <button
            onClick={() => setActiveTool("measure")}
            title="Measure Tool (ground distance)"
            className={`w-10 h-10 rounded flex items-center justify-center border transition-colors ${
              activeTool === "measure" ? "bg-primary text-white border-primary" : "text-text-muted hover:bg-surface-2 border-border"
            }`}
          >
            <Ruler className="w-4 h-4" strokeWidth={1.5} />
          </button>

          <div className="w-8 h-px bg-border my-1" />

          <button
            onClick={() => {
              setZoomLevel(1);
              setPanOffset({ x: 0, y: 0 });
            }}
            title="Reset Canvas View"
            className="w-10 h-10 rounded flex items-center justify-center border border-border text-text-muted hover:bg-surface-2"
          >
            <RotateCcw className="w-4 h-4" strokeWidth={1.5} />
          </button>
        </div>

        {/* Center: Waterfall Canvas & Overlays */}
        <div className="flex-1 flex flex-col min-w-0 bg-[#0F1722] relative">
          {/* Top Canvas Operational Bar */}
          <div className="min-h-[40px] bg-surface border-b border-border flex items-center justify-between px-3 py-1.5 gap-2 shrink-0 select-none">
            {/* Left: Active Line & Profile */}
            <div className="flex items-center gap-2 text-[12px] font-mono text-text">
              <span className="font-semibold text-text">{currentSurvey.name}</span>
              <span className="text-[11px] text-text-muted px-1.5 py-0.5 rounded bg-surface-2 border border-border">
                {currentSurvey.frequencyKhz || 450} kHz · Scale: ±{currentSurvey.rangeM || 75}m · Alt: {currentSurvey.altitudeM || 8.5}m
              </span>
            </div>

            {/* Right: Pipeline Filter, Status, and Candidate Counts */}
            <div className="flex items-center gap-2 flex-wrap sm:flex-nowrap">
              {/* Modality Warning Pill if Non-SSS */}
              {currentSurvey.modalityStatus === "NON_SSS_DETECTED" && (
                <div className="flex items-center gap-1.5 px-2 py-0.5 rounded bg-danger/10 border border-danger/40 text-danger text-[11px] font-mono font-medium shrink-0">
                  <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
                  <span>NON-SSS OPTICAL IMAGE · VETO ACTIVE</span>
                </div>
              )}

              {/* Segmented Control: Raw Proposals vs Physics-Verified */}
              <div className="flex items-center bg-surface-2 border border-border rounded p-0.5 shrink-0">
                <button
                  onClick={() => setPhysicsVerified(false)}
                  className={`px-2.5 py-1 text-[11px] font-medium rounded transition-colors ${
                    !physicsVerified
                      ? "bg-accent text-white font-semibold"
                      : "text-text-muted hover:text-text"
                  }`}
                >
                  Raw Proposals
                </button>
                <button
                  onClick={() => setPhysicsVerified(true)}
                  className={`px-2.5 py-1 text-[11px] font-medium rounded transition-colors flex items-center gap-1 ${
                    physicsVerified
                      ? "bg-primary text-white font-semibold"
                      : "text-text-muted hover:text-text"
                  }`}
                >
                  <ShieldCheck className="w-3.5 h-3.5" />
                  <span>Physics-Verified</span>
                </button>
              </div>

              {/* Verified Count Pill */}
              <div className="font-mono text-[11px] px-2.5 py-1 rounded border border-border bg-surface text-text whitespace-nowrap shrink-0">
                <span className="text-text-muted">{detections.length} candidates</span>
                <span className="text-border mx-1.5">|</span>
                <b className="text-success font-semibold">{verifiedCount} verified</b>
                <span className="text-border mx-1.5">|</span>
                <b className="text-text-muted">{suppressedCount} suppressed</b>
              </div>
            </div>
          </div>

          {/* Calibrated Acoustic Range Ruler Directly Aligned Above Waterfall Canvas */}
          <div className="h-6 bg-surface-2/90 border-b border-border px-6 flex items-center justify-between text-[10px] font-mono text-text-muted shrink-0 select-none">
            <span>PORT -{currentSurvey.rangeM || 75}m</span>
            <span className="hidden sm:inline">-50m</span>
            <span className="hidden md:inline">-25m</span>
            <span className="text-primary font-bold px-2 py-0.5 rounded bg-primary/10 border border-primary/20">
              NADIR 0m
            </span>
            <span className="hidden md:inline">+25m</span>
            <span className="hidden sm:inline">+50m</span>
            <span>STARBOARD +{currentSurvey.rangeM || 75}m</span>
          </div>

          {/* Canvas Viewport */}
          <div
            className="flex-1 relative overflow-hidden cursor-crosshair"
            onMouseDown={(e) => {
              if (activeTool === "pan") {
                setIsDragging(true);
                setDragStart({ x: e.clientX - panOffset.x, y: e.clientY - panOffset.y });
              }
            }}
            onMouseMove={(e) => {
              if (isDragging && activeTool === "pan") {
                setPanOffset({
                  x: e.clientX - dragStart.x,
                  y: e.clientY - dragStart.y,
                });
              }
            }}
            onMouseUp={() => setIsDragging(false)}
            onMouseLeave={() => setIsDragging(false)}
            onWheel={(e) => {
              e.preventDefault();
              const zoomFactor = e.deltaY < 0 ? 1.1 : 0.9;
              setZoomLevel((prev) => Math.max(0.6, Math.min(3.5, prev * zoomFactor)));
            }}
          >
            <canvas
              ref={canvasRef}
              width={780}
              height={480}
              onClick={handleCanvasClick}
              className="w-full h-full block object-contain"
            />

            {/* Collapsible Canvas Overlays Panel */}
            {!isOverlaysOpen ? (
              <button
                onClick={() => setIsOverlaysOpen(true)}
                className="absolute bottom-3 left-3 bg-surface/95 hover:bg-surface border border-border shadow-sm rounded px-2.5 py-1 text-[11px] font-medium text-text flex items-center gap-1.5 transition-colors select-none z-10"
                title="Expand Canvas Overlays Controls"
              >
                <Layers className="w-3.5 h-3.5 text-primary" />
                <span>Overlays ({[showDetections, showShadows, showMotionMask, showSuppressed, showGrid].filter(Boolean).length})</span>
              </button>
            ) : (
              <div className="absolute bottom-3 left-3 bg-surface border border-border rounded p-3 text-[12px] space-y-1.5 select-none shadow-md z-10 w-52">
                <div className="flex items-center justify-between pb-1 border-b border-border">
                  <span className="section-label text-[10px]">CANVAS OVERLAYS</span>
                  <button
                    onClick={() => setIsOverlaysOpen(false)}
                    className="text-text-muted hover:text-text text-[11px] p-0.5"
                    title="Minimize panel"
                  >
                    ✕
                  </button>
                </div>
                <label className="flex items-center gap-1.5 cursor-pointer text-text">
                  <input
                    type="checkbox"
                    checked={showDetections}
                    onChange={(e) => setShowDetections(e.target.checked)}
                    className="accent-primary"
                  />
                  <span>Detections</span>
                </label>
                <label className="flex items-center gap-1.5 cursor-pointer text-text">
                  <input
                    type="checkbox"
                    checked={showShadows}
                    onChange={(e) => setShowShadows(e.target.checked)}
                    className="accent-primary"
                  />
                  <span>Shadow regions</span>
                </label>
                <label className="flex items-center gap-1.5 cursor-pointer text-text">
                  <input
                    type="checkbox"
                    checked={showMotionMask}
                    onChange={(e) => setShowMotionMask(e.target.checked)}
                    className="accent-primary"
                  />
                  <span>Motion-artifact mask</span>
                </label>
                <label className="flex items-center gap-1.5 cursor-pointer text-text">
                  <input
                    type="checkbox"
                    checked={showSuppressed}
                    onChange={(e) => setShowSuppressed(e.target.checked)}
                    className="accent-primary"
                  />
                  <span>Suppressed detections</span>
                </label>
                <label className="flex items-center gap-1.5 cursor-pointer text-text">
                  <input
                    type="checkbox"
                    checked={showGrid}
                    onChange={(e) => setShowGrid(e.target.checked)}
                    className="accent-primary"
                  />
                  <span>Range grid</span>
                </label>
              </div>
            )}
          </div>
        </div>

        {/* Right: 380px Detections & Evidence Panel */}
        <div className="w-[380px] bg-surface border-l border-border flex flex-col shrink-0 select-none">
          {/* Panel Header & Tabs */}
          <div className="border-b border-border bg-surface-2 flex">
            <button
              onClick={() => setRightTab("detections")}
              className={`flex-1 py-2 text-[12px] font-medium border-b-2 text-center transition-colors ${
                rightTab === "detections"
                  ? "border-primary text-primary bg-surface font-semibold"
                  : "border-transparent text-text-muted hover:text-text"
              }`}
            >
              Detections ({detections.length})
            </button>
            <button
              onClick={() => setRightTab("evidence")}
              className={`flex-1 py-2 text-[12px] font-medium border-b-2 text-center transition-colors ${
                rightTab === "evidence"
                  ? "border-primary text-primary bg-surface font-semibold"
                  : "border-transparent text-text-muted hover:text-text"
              }`}
            >
              Evidence Card
            </button>
            <button
              onClick={() => setRightTab("log")}
              className={`flex-1 py-2 text-[12px] font-medium border-b-2 text-center transition-colors ${
                rightTab === "log"
                  ? "border-primary text-primary bg-surface font-semibold"
                  : "border-transparent text-text-muted hover:text-text"
              }`}
            >
              Log
            </button>
          </div>

          {/* Tab Content */}
          <div className="flex-1 overflow-y-auto p-3 text-[13px] space-y-3">
            {/* TAB 1: Detections List */}
            {rightTab === "detections" && (
              <div className="space-y-2">
                <div className="flex justify-between items-center text-[11px] text-text-muted">
                  <span className="section-label">CANDIDATES RANKED BY CONFIDENCE</span>
                  <span className="font-mono">{detections.filter((d) => !d.suppressed).length} ACTIVE</span>
                </div>

                {detections
                  .filter((d) => (physicsVerified ? showSuppressed || !d.suppressed : true))
                  .map((det) => {
                    const isSelected = selectedDetection?.id === det.id;
                    return (
                      <div
                        key={det.id}
                        onClick={() => {
                          setSelectedDetection(det);
                          setRightTab("evidence");
                        }}
                        className={`p-2.5 border rounded cursor-pointer transition-colors ${
                          isSelected
                            ? "border-primary bg-primary/5"
                            : det.suppressed
                            ? "border-danger/30 bg-danger/5 opacity-70"
                            : "border-border bg-surface hover:bg-surface-2"
                        }`}
                      >
                        <div className="flex justify-between items-start">
                          <div>
                            <span className="font-mono font-bold text-[12px] text-text">{det.id}</span>
                            <span className="mx-1 text-text-muted">·</span>
                            <span className="font-medium capitalize text-text">
                              {det.class === "submerged_bicycle" ? "Submerged Bicycle (Cycle)" : det.class.replace("_", " ")}
                            </span>
                          </div>
                          <span
                            className={`font-mono font-bold text-[12px] px-1.5 py-0.2 rounded ${
                              det.suppressed
                                ? "bg-danger/20 text-danger"
                                : "bg-success/20 text-success"
                            }`}
                          >
                            {Math.round(det.confidence)}%
                          </span>
                        </div>

                        <div className="mt-1 text-[11px] font-mono text-text-muted flex justify-between">
                          <span>
                            {det.geo.lat ? `${det.geo.lat.toFixed(5)}°N, ${det.geo.lon?.toFixed(5)}°E` : "Geo Unavailable"}
                          </span>
                          <span>H: {det.heightEstimateM ? `${det.heightEstimateM}m` : "N/A"}</span>
                        </div>

                        {det.suppressed && (
                          <div className="mt-1 text-[11px] text-danger font-mono bg-danger/10 p-1 rounded">
                            ⛔ {det.suppressionReason}
                          </div>
                        )}
                      </div>
                    );
                  })}
              </div>
            )}

            {/* TAB 2: Explainable Evidence Card */}
            {rightTab === "evidence" && selectedDetection && (
              <div className="space-y-3">
                <div className="p-3 bg-surface-2 border border-border rounded">
                  <div className="flex justify-between items-center">
                    <span className="font-mono font-bold text-[14px] text-text">{selectedDetection.id}</span>
                    <span
                      className={`font-mono font-bold text-[14px] ${
                        selectedDetection.suppressed ? "text-danger" : "text-success"
                      }`}
                    >
                      {Math.round(selectedDetection.confidence)}%
                    </span>
                  </div>
                  <div className="text-[12px] text-text-muted capitalize mt-0.5">
                    Class: <b className="text-text">{selectedDetection.class === "submerged_bicycle" ? "Submerged Bicycle (Cycle)" : selectedDetection.class === "unknown_manmade" ? "Unknown Anthropogenic Structure" : selectedDetection.class.replace("_", " ")}</b>
                  </div>
                  <div className="text-[11px] font-mono text-text-muted mt-1 flex justify-between">
                    <span>
                      {selectedDetection.geo.status === "AVAILABLE"
                        ? `Lat: ${selectedDetection.geo.lat}°N, Lon: ${selectedDetection.geo.lon}°E`
                        : "Georeference: UNAVAILABLE (Image-only mode)"}
                    </span>
                    <span>
                      {selectedDetection.mergedComponentsCount && selectedDetection.mergedComponentsCount > 1
                        ? `Fused: ${selectedDetection.mergedComponentsCount} components`
                        : "Single Echo"}
                    </span>
                  </div>
                  {selectedDetection.diverSearchBoxM && (
                    <div className="text-[10px] font-mono text-primary mt-1 border-t border-border pt-1">
                      Diver Search Box: {selectedDetection.diverSearchBoxM.width}m × {selectedDetection.diverSearchBoxM.height}m (2 × r95)
                    </div>
                  )}
                </div>

                {/* Section 59: UI Decision Audit Card */}
                {selectedDetection.overrideOccurred && (
                  <div className="p-2.5 bg-amber-500/10 border border-amber-500/30 rounded text-[11px] space-y-1">
                    <div className="font-bold text-amber-700 flex items-center gap-1">
                      <SlidersHorizontal className="w-3.5 h-3.5" />
                      <span>PHYSICS &amp; MORPHOLOGY OVERRIDE ACTIVE</span>
                    </div>
                    <div className="text-text-muted">
                      Raw Proposal: <span className="font-mono font-bold text-text">{selectedDetection.rawClass?.replace("_", " ")}</span> ({selectedDetection.rawConfidence}%)
                    </div>
                    <div className="text-text font-medium text-[11px]">
                      {selectedDetection.overrideLog || selectedDetection.decisionReason}
                    </div>
                  </div>
                )}

                {/* Section 40: Explainable Decision Log */}
                {selectedDetection.decisionReason && (
                  <div className="p-2.5 bg-surface-2 border border-border rounded text-[11px] space-y-1">
                    <div className="section-label">INTERPRETABLE DECISION REASON</div>
                    <p className="text-text leading-relaxed">
                      {selectedDetection.decisionReason}
                    </p>
                  </div>
                )}

                {selectedDetection.suppressed && (
                  <div className="p-2.5 bg-danger/10 border border-danger/40 rounded text-[11px] text-danger font-mono">
                    <b>SUPPRESSION REASON:</b>
                    <br />
                    {selectedDetection.suppressionReason}
                  </div>
                )}

                {/* Section 45: Competing Class Evidence Table */}
                {selectedDetection.classScores && (
                  <div className="p-2.5 bg-surface-2 border border-border rounded space-y-1.5">
                    <div className="flex justify-between items-center">
                      <span className="section-label">COMPETING CLASS EVIDENCE</span>
                      <span className="text-[10px] font-mono text-primary font-semibold">OPEN-SET</span>
                    </div>
                    <div className="space-y-1 text-[11px] font-mono">
                      {Object.entries(selectedDetection.classScores).map(([cls, score]) => {
                        const isWinner = cls === selectedDetection.class;
                        return (
                          <div
                            key={cls}
                            className={`flex justify-between items-center px-1.5 py-0.5 rounded ${
                              isWinner ? "bg-primary/10 text-primary font-bold border border-primary/20" : "text-text-muted"
                            }`}
                          >
                            <span>{cls === "unknown_manmade" ? "unknown_anthropogenic" : cls.replace("_", " ")}</span>
                            <span>{((score ?? 0) * 100).toFixed(0)}%</span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}

                {/* Section 44: Multi-Head Evidence Stack */}
                <div className="space-y-2 p-2.5 bg-surface-2 border border-border rounded">
                  <div className="section-label">MULTI-HEAD MORPHOLOGY &amp; PHYSICS EVIDENCE</div>

                  {/* Circular / Annular */}
                  <div className="space-y-0.5">
                    <div className="flex justify-between text-[11px]">
                      <span className="text-text font-medium">Circular / Annular Head</span>
                      <span className="font-mono text-text">
                        {((selectedDetection.comprehensiveEvidence?.circular ?? 0) * 100).toFixed(0)}%
                      </span>
                    </div>
                    <div className="h-1 bg-surface rounded overflow-hidden">
                      <div
                        className="h-full bg-amber-500"
                        style={{ width: `${(selectedDetection.comprehensiveEvidence?.circular ?? 0) * 100}%` }}
                      />
                    </div>
                  </div>

                  {/* Truss / Framework */}
                  <div className="space-y-0.5">
                    <div className="flex justify-between text-[11px]">
                      <span className="text-text font-medium">Tubular / Truss Framework Head</span>
                      <span className="font-mono text-text">
                        {((selectedDetection.comprehensiveEvidence?.truss ?? 0) * 100).toFixed(0)}%
                      </span>
                    </div>
                    <div className="h-1 bg-surface rounded overflow-hidden">
                      <div
                        className="h-full bg-amber-600"
                        style={{ width: `${(selectedDetection.comprehensiveEvidence?.truss ?? 0) * 100}%` }}
                      />
                    </div>
                  </div>

                  {/* Net Signature (Rope & Mesh) */}
                  <div className="space-y-0.5">
                    <div className="flex justify-between text-[11px]">
                      <span className="text-text font-medium">Net Signature (Rope / Mesh / Floats)</span>
                      <span className="font-mono text-text">
                        {((selectedDetection.comprehensiveEvidence?.mesh ?? 0) * 100).toFixed(0)}%
                      </span>
                    </div>
                    <div className="h-1 bg-surface rounded overflow-hidden">
                      <div
                        className="h-full bg-orange-600"
                        style={{ width: `${(selectedDetection.comprehensiveEvidence?.mesh ?? 0) * 100}%` }}
                      />
                    </div>
                  </div>

                  {/* Linear Pipeline */}
                  <div className="space-y-0.5">
                    <div className="flex justify-between text-[11px]">
                      <span className="text-text font-medium">Linear Pipeline / Conduit</span>
                      <span className="font-mono text-text">
                        {((selectedDetection.comprehensiveEvidence?.linear ?? 0) * 100).toFixed(0)}%
                      </span>
                    </div>
                    <div className="h-1 bg-surface rounded overflow-hidden">
                      <div
                        className="h-full bg-blue-600"
                        style={{ width: `${(selectedDetection.comprehensiveEvidence?.linear ?? 0) * 100}%` }}
                      />
                    </div>
                  </div>

                  {/* Anthropogenic Anomaly */}
                  <div className="space-y-0.5">
                    <div className="flex justify-between text-[11px]">
                      <span className="text-text font-medium">Anthropogenic Specular Evidence</span>
                      <span className="font-mono text-text">
                        {((selectedDetection.comprehensiveEvidence?.anthropogenic ?? 0.8) * 100).toFixed(0)}%
                      </span>
                    </div>
                    <div className="h-1 bg-surface rounded overflow-hidden">
                      <div
                        className="h-full bg-purple-600"
                        style={{ width: `${(selectedDetection.comprehensiveEvidence?.anthropogenic ?? 0.8) * 100}%` }}
                      />
                    </div>
                  </div>

                  {/* Shadow Relief */}
                  <div className="space-y-0.5">
                    <div className="flex justify-between text-[11px]">
                      <span className="text-text font-medium">Shadow Relief Height</span>
                      <span className="font-mono font-bold text-success">
                        {selectedDetection.heightEstimateM !== null ? `${selectedDetection.heightEstimateM}m` : "None / Flat"}
                      </span>
                    </div>
                    <div className="h-1 bg-surface rounded overflow-hidden">
                      <div
                        className="h-full bg-success"
                        style={{ width: `${(selectedDetection.evidence.shc ?? 0.5) * 100}%` }}
                      />
                    </div>
                  </div>
                </div>

                {/* Operator Review Actions */}

                {/* Operator Review Actions */}
                <div className="pt-3 border-t border-border space-y-2">
                  <div className="section-label">OPERATOR REVIEW ACTION</div>
                  <div className="grid grid-cols-2 gap-2">
                    <button
                      onClick={() => alert(`Target ${selectedDetection.id} accepted for clearance follow-up.`)}
                      className="px-2.5 py-1.5 bg-success text-white text-[12px] font-medium rounded hover:bg-success/90"
                    >
                      Accept Target
                    </button>
                    <button
                      onClick={() => alert(`Target ${selectedDetection.id} rejected as false alarm.`)}
                      className="px-2.5 py-1.5 bg-danger text-white text-[12px] font-medium rounded hover:bg-danger/90"
                    >
                      Reject Target
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* TAB 3: Pipeline Log */}
            {rightTab === "log" && (
              <div className="space-y-2 font-mono text-[11px] text-text-muted">
                <div className="section-label">SURVEY EXECUTION AUDIT LOG</div>
                <div className="p-2 bg-surface-2 rounded border border-border space-y-1">
                  <div>[14:02:11 UTC] Ingestion: parsed pyxtf headers (1680 pings)</div>
                  <div>[14:02:12 UTC] Slant-to-ground range projection: 75.0m</div>
                  <div>[14:02:12 UTC] Enhanced Lee filter applied (window 5x5)</div>
                  <div>[14:02:13 UTC] Motion mask: 142 corrupted pings excluded</div>
                  <div>[14:02:14 UTC] YOLOv8n INT8 inferred: 14 candidates</div>
                  <div>[14:02:14 UTC] EchoSift SHC: 8 candidates failed height test</div>
                  <div>[14:02:15 UTC] Spatial join: 3 targets corroborated in Line 08</div>
                  <div>[14:02:15 UTC] Finalized: 6 verified, 8 suppressed</div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Bottom: 120px Telemetry Strip (Three Recharts: Roll/Pitch, Altitude, Ping Correlation) */}
      <div className="h-[120px] bg-surface border-t border-border flex shrink-0 select-none">
        {/* Chart 1: Roll / Pitch */}
        <div className="flex-1 p-2 border-r border-border flex flex-col min-w-0">
          <div className="flex justify-between items-center text-[10px] font-mono text-text-muted mb-1">
            <span className="font-semibold text-text">ROLL / PITCH (deg)</span>
            <span>Threshold: ±5°</span>
          </div>
          <div className="flex-1 min-h-0">
            {telemetryData.length > 0 && telemetryData.some((t) => t.roll !== undefined || t.pitch !== undefined) ? (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={telemetryData} margin={{ top: 4, right: 10, left: -16, bottom: 2 }}>
                  <YAxis domain={[-8, 8]} tick={{ fontSize: 9 }} stroke="#8FA1B4" />
                  <XAxis dataKey="ping" hide />
                  <RechartsTooltip contentStyle={{ fontSize: "11px", padding: "4px 8px" }} />
                  <ReferenceArea y1={5} y2={8} fill="#A61B1B" fillOpacity={0.15} />
                  <ReferenceArea y1={-8} y2={-5} fill="#A61B1B" fillOpacity={0.15} />
                  <Line type="monotone" dataKey="roll" stroke="#1D4ED8" dot={false} strokeWidth={1.5} />
                  <Line type="monotone" dataKey="pitch" stroke="#B45309" dot={false} strokeWidth={1.5} />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div className="w-full h-full flex items-center justify-center text-[11px] text-text-muted font-mono">
                Telemetry unavailable
              </div>
            )}
          </div>
        </div>

        {/* Chart 2: Towfish Altitude */}
        <div className="flex-1 p-2 border-r border-border flex flex-col min-w-0">
          <div className="flex justify-between items-center text-[10px] font-mono text-text-muted mb-1">
            <span className="font-semibold text-text">TOWFISH ALTITUDE (m)</span>
            <span>Nominal: {currentSurvey.altitudeM || 8.2}m</span>
          </div>
          <div className="flex-1 min-h-0">
            {telemetryData.length > 0 && telemetryData.some((t) => t.altitude !== undefined) ? (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={telemetryData} margin={{ top: 4, right: 10, left: -16, bottom: 2 }}>
                  <YAxis domain={[5, 14]} tick={{ fontSize: 9 }} stroke="#8FA1B4" />
                  <XAxis dataKey="ping" hide />
                  <RechartsTooltip contentStyle={{ fontSize: "11px", padding: "4px 8px" }} />
                  <Line type="monotone" dataKey="altitude" stroke="#0F766E" dot={false} strokeWidth={1.5} />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div className="w-full h-full flex items-center justify-center text-[11px] text-text-muted font-mono">
                Telemetry unavailable
              </div>
            )}
          </div>
        </div>

        {/* Chart 3: Ping Correlation */}
        <div className="flex-1 p-2 flex flex-col min-w-0">
          <div className="flex justify-between items-center text-[10px] font-mono text-text-muted mb-1">
            <span className="font-semibold text-text">PING CROSS-CORRELATION (rho)</span>
            <span>Veto: &lt; 0.60</span>
          </div>
          <div className="flex-1 min-h-0">
            {telemetryData.length > 0 && telemetryData.some((t) => t.correlation !== undefined) ? (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={telemetryData} margin={{ top: 4, right: 10, left: -16, bottom: 2 }}>
                  <YAxis domain={[0, 1]} tick={{ fontSize: 9 }} stroke="#8FA1B4" />
                  <XAxis dataKey="ping" hide />
                  <RechartsTooltip contentStyle={{ fontSize: "11px", padding: "4px 8px" }} />
                  <ReferenceArea y1={0} y2={0.6} fill="#A61B1B" fillOpacity={0.15} />
                  <Line type="monotone" dataKey="correlation" stroke="#1B6E3A" dot={false} strokeWidth={1.5} />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div className="w-full h-full flex items-center justify-center text-[11px] text-text-muted font-mono">
                Telemetry unavailable
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
