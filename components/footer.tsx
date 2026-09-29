import React from "react";

export function Footer() {
  return (
    <footer className="h-[28px] bg-surface-2 border-t border-border px-4 flex items-center justify-between text-[11px] text-text-muted select-none shrink-0 font-mono">
      <div>
        Prototype build · PS 26057 · Data provenance: see Data tab · Coordinates WGS84 · Not for navigation.
      </div>
      <div className="hidden sm:block">
        NIOT / MoES · SagarNetra v1.0-prod
      </div>
    </footer>
  );
}
