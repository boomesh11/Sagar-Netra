"use client";

import React from "react";
import { useAppState, NavTab } from "@/lib/app-state";
import {
  FolderKanban,
  Crosshair,
  MapPin,
  FileText,
  Database,
  Grid,
  Layers,
  Cpu,
  Activity,
  Info,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  BookOpen,
} from "lucide-react";

export function Sidebar() {
  const { activeTab, setActiveTab, sidebarCollapsed, setSidebarCollapsed } = useAppState();

  const mainNav: { id: NavTab; label: string; icon: React.ElementType }[] = [
    { id: "surveys", label: "Surveys", icon: FolderKanban },
    { id: "analysis", label: "Analysis", icon: Crosshair },
    { id: "map", label: "Map", icon: MapPin },
    { id: "reports", label: "Reports & Export", icon: FileText },
    { id: "data", label: "Data & Provenance", icon: Database },
    { id: "guide", label: "User Guide", icon: BookOpen },
  ];

  const advancedNav: { id: NavTab; label: string; icon: React.ElementType }[] = [
    { id: "coverage", label: "Coverage Grid", icon: Grid },
    { id: "change-detection", label: "Change Detection", icon: Layers },
    { id: "synthetic-bench", label: "Synthetic Bench", icon: Cpu },
  ];

  const systemNav: { id: NavTab; label: string; icon: React.ElementType }[] = [
    { id: "edge-profile", label: "Edge profile", icon: Activity },
    { id: "model-info", label: "Model info", icon: Info },
    { id: "tests", label: "Tests", icon: CheckCircle2 },
  ];

  return (
    <aside
      className={`h-full bg-surface border-r border-border flex flex-col justify-between shrink-0 transition-all duration-200 select-none ${
        sidebarCollapsed ? "w-[64px]" : "w-[240px]"
      }`}
    >
      <div className="flex-1 py-3 overflow-y-auto">
        {/* Main Section */}
        <div className="px-3 mb-2">
          {!sidebarCollapsed && (
            <div className="section-label px-2 mb-1.5">NAVIGATION</div>
          )}
          <nav className="space-y-0.5">
            {mainNav.map((item) => {
              const Icon = item.icon;
              const isActive = activeTab === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => setActiveTab(item.id)}
                  title={sidebarCollapsed ? item.label : undefined}
                  className={`w-full flex items-center gap-2.5 px-2.5 py-2 rounded text-[13px] font-medium transition-colors ${
                    isActive
                      ? "bg-primary text-white"
                      : "text-text hover:bg-surface-2"
                  }`}
                >
                  <Icon className="w-4 h-4 shrink-0" strokeWidth={1.5} />
                  {!sidebarCollapsed && <span>{item.label}</span>}
                </button>
              );
            })}
          </nav>
        </div>

        <div className="h-px bg-border my-2 mx-3" />

        {/* Advanced Section */}
        <div className="px-3 mb-2">
          {!sidebarCollapsed && (
            <div className="section-label px-2 mb-1.5">ADVANCED</div>
          )}
          <nav className="space-y-0.5">
            {advancedNav.map((item) => {
              const Icon = item.icon;
              const isActive = activeTab === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => setActiveTab(item.id)}
                  title={sidebarCollapsed ? item.label : undefined}
                  className={`w-full flex items-center gap-2.5 px-2.5 py-2 rounded text-[13px] font-medium transition-colors ${
                    isActive
                      ? "bg-primary text-white"
                      : "text-text hover:bg-surface-2"
                  }`}
                >
                  <Icon className="w-4 h-4 shrink-0" strokeWidth={1.5} />
                  {!sidebarCollapsed && <span>{item.label}</span>}
                </button>
              );
            })}
          </nav>
        </div>

        <div className="h-px bg-border my-2 mx-3" />

        {/* System Section */}
        <div className="px-3">
          {!sidebarCollapsed && (
            <div className="section-label px-2 mb-1.5">SYSTEM</div>
          )}
          <nav className="space-y-0.5">
            {systemNav.map((item) => {
              const Icon = item.icon;
              const isActive = activeTab === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => setActiveTab(item.id)}
                  title={sidebarCollapsed ? item.label : undefined}
                  className={`w-full flex items-center gap-2.5 px-2.5 py-2 rounded text-[13px] font-medium transition-colors ${
                    isActive
                      ? "bg-primary text-white"
                      : "text-text hover:bg-surface-2"
                  }`}
                >
                  <Icon className="w-4 h-4 shrink-0" strokeWidth={1.5} />
                  {!sidebarCollapsed && <span>{item.label}</span>}
                </button>
              );
            })}
          </nav>
        </div>
      </div>

      {/* Collapse Toggle at bottom */}
      <div className="p-2 border-t border-border">
        <button
          onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
          className="w-full flex items-center justify-center p-1.5 text-text-muted hover:text-text hover:bg-surface-2 rounded text-[12px] border border-border"
          title={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {sidebarCollapsed ? (
            <ChevronRight className="w-4 h-4" strokeWidth={1.5} />
          ) : (
            <div className="flex items-center gap-2">
              <ChevronLeft className="w-4 h-4" strokeWidth={1.5} />
              <span className="text-[11px] font-mono">COLLAPSE RAIL</span>
            </div>
          )}
        </button>
      </div>
    </aside>
  );
}
