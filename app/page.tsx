"use client";

import React from "react";
import { useAppState } from "@/lib/app-state";
import { Header } from "@/components/header";
import { Sidebar } from "@/components/sidebar";
import { Footer } from "@/components/footer";

import { SurveysView } from "@/components/views/surveys-view";
import { AnalysisView } from "@/components/views/analysis-view";
import { MapView } from "@/components/views/map-view";
import { ReportsView } from "@/components/views/reports-view";
import { DataProvenanceView } from "@/components/views/data-provenance-view";
import { CoverageGridView } from "@/components/views/coverage-grid-view";
import { ChangeDetectionView } from "@/components/views/change-detection-view";
import { SyntheticBenchView } from "@/components/views/synthetic-bench-view";
import { SystemView } from "@/components/views/system-view";
import { GuideView } from "@/components/views/guide-view";

export default function Home() {
  const { activeTab } = useAppState();

  return (
    <div className="flex flex-col h-screen w-screen overflow-hidden bg-bg">
      {/* 56px Fixed Header */}
      <Header />

      {/* Main Middle Row: Sidebar + Active View */}
      <div className="flex flex-1 min-h-0 overflow-hidden">
        <Sidebar />

        <main className="flex-1 min-h-0 min-w-0 overflow-hidden bg-bg">
          {activeTab === "surveys" && <SurveysView />}
          {activeTab === "analysis" && <AnalysisView />}
          {activeTab === "map" && <MapView />}
          {activeTab === "reports" && <ReportsView />}
          {activeTab === "data" && <DataProvenanceView />}
          {activeTab === "coverage" && <CoverageGridView />}
          {activeTab === "change-detection" && <ChangeDetectionView />}
          {activeTab === "synthetic-bench" && <SyntheticBenchView />}
          {activeTab === "edge-profile" && <SystemView subTab="edge-profile" />}
          {activeTab === "model-info" && <SystemView subTab="model-info" />}
          {activeTab === "tests" && <SystemView subTab="tests" />}
          {activeTab === "guide" && <GuideView />}
        </main>
      </div>

      {/* 28px Fixed Footer */}
      <Footer />
    </div>
  );
}
