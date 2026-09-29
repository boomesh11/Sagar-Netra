"use client";

import React, { useState, useEffect } from "react";
import { useAppState } from "@/lib/app-state";
import { Sun, Moon, HelpCircle, WifiOff, BookOpen } from "lucide-react";

export function Header() {
  const { currentSurvey, theme, toggleTheme, setActiveTab } = useAppState();
  const [utcTime, setUtcTime] = useState<string>("");
  const [showHelpModal, setShowHelpModal] = useState(false);

  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      const iso = now.toISOString().replace("T", " ").substring(0, 19) + " UTC";
      setUtcTime(iso);
    };
    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, []);

  return (
    <>
      <header className="h-[56px] bg-surface border-b border-border flex items-center justify-between px-4 select-none shrink-0 z-30">
        {/* Left: NIOT wordmark + Brand title + Divider + Survey name */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <span className="bg-primary text-white text-[10px] font-bold tracking-wider px-1.5 py-0.5 rounded-sm">
              NIOT / MoES
            </span>
            <span className="font-semibold text-[14px] text-text">
              SagarNetra
            </span>
            <span className="text-text-muted text-[13px] hidden md:inline">
              · Marine Debris Detection System
            </span>
          </div>

          <div className="h-4 w-px bg-border mx-1" />

          <div className="flex items-center gap-1.5 text-[13px] text-text-muted font-mono">
            <span className="text-text font-medium">{currentSurvey.name}</span>
            <span className="text-[11px] bg-surface-2 px-1.5 py-0.5 rounded border border-border">
              {currentSurvey.id}
            </span>
          </div>
        </div>

        {/* Right: Offline pill, UTC clock, Guide button, Theme toggle, Help */}
        <div className="flex items-center gap-3">
          {/* Connection status pill */}
          <div className="flex items-center gap-1.5 px-2 py-1 bg-surface-2 border border-border rounded text-[12px] text-text-muted">
            <span className="w-2 h-2 rounded-full bg-success" />
            <WifiOff className="w-3.5 h-3.5 text-text-muted" />
            <span className="hidden sm:inline">Local · Offline mode</span>
          </div>

          {/* UTC Clock in IBM Plex Mono */}
          <div className="text-[12px] font-mono text-text-muted hidden md:block">
            {utcTime || "2026-09-26 14:00:00 UTC"}
          </div>

          {/* Professional Guide Button */}
          <button
            onClick={() => setActiveTab("guide")}
            title="Open Hydrographic Operator Reference Manual"
            className="flex items-center gap-1.5 px-2.5 py-1 text-text hover:bg-surface-2 rounded border border-border text-[12px] font-medium transition-colors"
          >
            <BookOpen className="w-3.5 h-3.5 text-primary" />
            <span>Guide</span>
          </button>

          {/* Theme Toggle */}
          <button
            onClick={toggleTheme}
            title={theme === "light" ? "Switch to Dark Survey-Room mode" : "Switch to Light mode"}
            className="p-1.5 text-text-muted hover:text-text hover:bg-surface-2 rounded border border-border transition-colors"
          >
            {theme === "light" ? (
              <Moon className="w-4 h-4" />
            ) : (
              <Sun className="w-4 h-4" />
            )}
          </button>

          {/* Help Modal Trigger */}
          <button
            onClick={() => setShowHelpModal(true)}
            title="System Documentation & Shortcuts"
            className="p-1.5 text-text-muted hover:text-text hover:bg-surface-2 rounded border border-border transition-colors"
          >
            <HelpCircle className="w-4 h-4" />
          </button>
        </div>
      </header>

      {/* Help Modal */}
      {showHelpModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="bg-surface border border-border rounded w-full max-w-lg p-5">
            <div className="flex justify-between items-center pb-3 border-b border-border">
              <span className="section-label">SYSTEM REFERENCE MANUAL</span>
              <button
                onClick={() => setShowHelpModal(false)}
                className="text-text-muted hover:text-text text-[13px] font-mono"
              >
                ✕ ESC
              </button>
            </div>
            <div className="py-4 space-y-3 text-[13px] text-text">
              <p>
                <b>SagarNetra</b> is an operational hydrographic analysis workstation engineered for the National Institute of Ocean Technology (NIOT), Ministry of Earth Sciences (MoES), under Problem Statement 26057.
              </p>
              <div className="p-3 bg-surface-2 rounded border border-border space-y-1 font-mono text-[12px]">
                <div><b>Navigation Hotkeys:</b></div>
                <div>1: Surveys | 2: Analysis | 3: Map | 4: Reports</div>
                <div>P: Toggle Physics Verification on/off</div>
                <div>Space: Pan tool | M: Measure tool</div>
              </div>
              <p className="text-text-muted text-[12px]">
                Acoustic height formula: <code>h = (L_s · H) / (R + L_s)</code>. Coordinates derived with WGS84 UTM Zone 44N projection. Strictly offline; zero cloud telemetry.
              </p>
            </div>
            <div className="flex justify-between items-center pt-3 border-t border-border">
              <button
                onClick={() => {
                  setShowHelpModal(false);
                  setActiveTab("guide");
                }}
                className="flex items-center gap-1.5 text-[12px] text-primary hover:text-primary-hover font-medium"
              >
                <BookOpen className="w-3.5 h-3.5" />
                <span>Open Full Operator Manual</span>
              </button>
              <button
                onClick={() => setShowHelpModal(false)}
                className="px-3 py-1.5 bg-primary text-white text-[13px] rounded hover:bg-primary-hover"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
