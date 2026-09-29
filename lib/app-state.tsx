"use client";

import React, { createContext, useContext, useState, useEffect } from "react";
import { Survey, Detection } from "@/types/survey";
import { SEED_SURVEYS, SEED_DETECTIONS_LINE_07 } from "@/lib/engine/inference";

export type NavTab = 
  | "surveys"
  | "analysis"
  | "map"
  | "reports"
  | "data"
  | "coverage"
  | "change-detection"
  | "synthetic-bench"
  | "edge-profile"
  | "model-info"
  | "tests"
  | "guide";

export const EMPTY_SURVEY: Survey = {
  id: "NO_ACTIVE_SURVEY",
  name: "No Survey Loaded",
  date: "—",
  platform: "—",
  sonarModel: "—",
  frequencyKhz: 0,
  rangeM: 0,
  altitudeM: 0,
  lineLengthKm: 0,
  pingCount: 0,
  geoStatus: "UNAVAILABLE",
  status: "READY",
  verifiedCount: 0,
  suppressedCount: 0,
  coverageKm2: 0,
  operator: "None",
  areaLocation: "No survey loaded. Ingest raw sonar waterfall data to begin.",
  utmZone: "UNAVAILABLE",
  isDemoSynthetic: false,
};

interface AppStateContextType {
  activeTab: NavTab;
  setActiveTab: (tab: NavTab) => void;
  surveys: Survey[];
  setSurveys: React.Dispatch<React.SetStateAction<Survey[]>>;
  currentSurvey: Survey;
  setCurrentSurvey: (survey: Survey) => void;
  detections: Detection[];
  setDetections: React.Dispatch<React.SetStateAction<Detection[]>>;
  selectedDetection: Detection | null;
  setSelectedDetection: (det: Detection | null) => void;
  loadSyntheticDemo: () => void;
  physicsVerified: boolean;
  setPhysicsVerified: (val: boolean) => void;
  sidebarCollapsed: boolean;
  setSidebarCollapsed: (val: boolean) => void;
  theme: "light" | "dark";
  toggleTheme: () => void;
  isProcessing: boolean;
  setIsProcessing: (val: boolean) => void;
  processingProgress: number;
  setProcessingProgress: React.Dispatch<React.SetStateAction<number>>;
  currentStepIndex: number;
  setCurrentStepIndex: React.Dispatch<React.SetStateAction<number>>;
  currentStepLog: string;
  setCurrentStepLog: React.Dispatch<React.SetStateAction<string>>;
  uploadedImageUrl: string | null;
  setUploadedImageUrl: (url: string | null) => void;
  uploadedImageElement: HTMLImageElement | null;
  setUploadedImageElement: (img: HTMLImageElement | null) => void;
}

const AppStateContext = createContext<AppStateContextType | undefined>(undefined);

export function AppStateProvider({ children }: { children: React.ReactNode }) {
  const [activeTab, setActiveTab] = useState<NavTab>("surveys");
  const [surveys, setSurveys] = useState<Survey[]>([]);
  const [currentSurvey, setCurrentSurvey] = useState<Survey>(EMPTY_SURVEY);
  const [detections, setDetections] = useState<Detection[]>([]);
  const [selectedDetection, setSelectedDetection] = useState<Detection | null>(null);

  const loadSyntheticDemo = () => {
    setSurveys(SEED_SURVEYS);
    setCurrentSurvey(SEED_SURVEYS[0]);
    setDetections(SEED_DETECTIONS_LINE_07);
    setSelectedDetection(SEED_DETECTIONS_LINE_07[0]);
  };
  const [physicsVerified, setPhysicsVerified] = useState<boolean>(true);
  const [sidebarCollapsed, setSidebarCollapsed] = useState<boolean>(false);
  const [theme, setTheme] = useState<"light" | "dark">("light");

  // Pipeline simulation state
  const [isProcessing, setIsProcessing] = useState(false);
  const [processingProgress, setProcessingProgress] = useState(0);
  const [currentStepIndex, setCurrentStepIndex] = useState(0);
  const [currentStepLog, setCurrentStepLog] = useState("");
  const [uploadedImageUrl, setUploadedImageUrl] = useState<string | null>(null);
  const [uploadedImageElement, setUploadedImageElement] = useState<HTMLImageElement | null>(null);

  const toggleTheme = () => {
    setTheme((prev) => {
      const next = prev === "light" ? "dark" : "light";
      if (typeof document !== "undefined") {
        if (next === "dark") {
          document.documentElement.classList.add("dark");
        } else {
          document.documentElement.classList.remove("dark");
        }
      }
      return next;
    });
  };

  return (
    <AppStateContext.Provider
      value={{
        activeTab,
        setActiveTab,
        surveys,
        setSurveys,
        currentSurvey,
        setCurrentSurvey,
        detections,
        setDetections,
        selectedDetection,
        setSelectedDetection,
        loadSyntheticDemo,
        physicsVerified,
        setPhysicsVerified,
        sidebarCollapsed,
        setSidebarCollapsed,
        theme,
        toggleTheme,
        isProcessing,
        setIsProcessing,
        processingProgress,
        setProcessingProgress,
        currentStepIndex,
        setCurrentStepIndex,
        currentStepLog,
        setCurrentStepLog,
        uploadedImageUrl,
        setUploadedImageUrl,
        uploadedImageElement,
        setUploadedImageElement,
      }}
    >
      {children}
    </AppStateContext.Provider>
  );
}

export function useAppState() {
  const context = useContext(AppStateContext);
  if (!context) {
    throw new Error("useAppState must be used within an AppStateProvider");
  }
  return context;
}
