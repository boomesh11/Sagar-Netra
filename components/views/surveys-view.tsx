"use client";

import React, { useState, useEffect } from "react";
import { useAppState } from "@/lib/app-state";
import { Survey } from "@/types/survey";
import { uploadAndAnalyzeSurvey, fetchSurveys } from "@/lib/api";
import { checkImageModality, ModalityCheckResult } from "@/lib/sonar-detector";
import {
  UploadCloud,
  FileCheck2,
  FileCode,
  FileSpreadsheet,
  AlertCircle,
  AlertTriangle,
  Play,
  Download,
  Trash2,
  ExternalLink,
  CheckCircle,
  X,
  Plus,
  Loader2,
  Sparkles,
  FolderOpen,
} from "lucide-react";

interface UploadedFileItem {
  file: File;
  name: string;
  typeDetected: string;
  sizeFormatted: string;
  status: "Parsed" | "Needs navigation" | "Non-SSS (Optical)" | "Unsupported";
}

export function SurveysView() {
  const {
    surveys,
    setSurveys,
    setCurrentSurvey,
    setDetections,
    setSelectedDetection,
    setActiveTab,
    setIsProcessing,
    setProcessingProgress,
    currentStepIndex,
    setUploadedImageUrl,
    setUploadedImageElement,
    loadSyntheticDemo,
  } = useAppState();

  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [currentStep, setCurrentStep] = useState<1 | 2 | 3>(1);
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFileItem[]>([]);
  const [dragOver, setDragOver] = useState(false);

  // Real image upload and modality validation state
  const [loadedImageObj, setLoadedImageObj] = useState<HTMLImageElement | null>(null);
  const [loadedImageUrl, setLoadedImageUrl] = useState<string | null>(null);
  const [imageStats, setImageStats] = useState<{ width: number; height: number } | null>(null);
  const [modalityCheck, setModalityCheck] = useState<ModalityCheckResult | null>(null);

  // Backend state
  const [backendError, setBackendError] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);

  // Fetch initial surveys from backend SQLite on mount
  useEffect(() => {
    fetchSurveys()
      .then((data) => {
        if (data && data.length > 0) {
          setSurveys(data);
        }
      })
      .catch((err) => {
        console.warn("Backend offline during surveys fetch:", err.message);
      });
  }, [setSurveys]);

  // Form details
  const [surveyName, setSurveyName] = useState("");
  const [vessel, setVessel] = useState("RV Samudra Ratnakar");
  const [sonarModel, setSonarModel] = useState("EdgeTech 4200");
  const [frequency, setFrequency] = useState("400");
  const [rangeM, setRangeM] = useState("75.0");
  const [altitudeM, setAltitudeM] = useState("8.5");
  const [areaLocation, setAreaLocation] = useState("Coastal Survey Transect");
  const [date, setDate] = useState("2026-09-26");
  const [operator, setOperator] = useState("Hydrographic Survey Team");
  const [utmZone, setUtmZone] = useState("UTM Zone 44N (Centroid 17.68°N, 83.35°E)");

  // Processing options
  const [despeckle, setDespeckle] = useState<"Lee" | "Frost" | "None">("Lee");
  const [motionThreshold, setMotionThreshold] = useState("5");
  const [tileSize, setTileSize] = useState("640");
  const [confThreshold, setConfThreshold] = useState("0.40");
  const [showSuppressed, setShowSuppressed] = useState(true);
  const [matchingRadius, setMatchingRadius] = useState("5");
  const [deploymentProfile, setDeploymentProfile] = useState<"Shore FP32" | "Onboard INT8 (Jetson Orin Nano)">("Shore FP32");

  // File handling
  const handleFiles = (fileList: FileList | File[] | null) => {
    if (!fileList) return;
    const filesArr = Array.from(fileList);
    const newItems: UploadedFileItem[] = filesArr.map((f) => {
      const ext = f.name.split(".").pop()?.toLowerCase();
      let typeDetected = "Unknown";
      let status: "Parsed" | "Needs navigation" | "Unsupported" = "Parsed";

      if (ext === "xtf" || ext === "jsf") {
        typeDetected = ext.toUpperCase() + " Native Sonar Log";
        status = "Parsed";
      } else if (["tif", "tiff", "png", "jpg", "jpeg", "webp"].includes(ext || "")) {
        typeDetected = ext?.toUpperCase() + " Sonar Raster Image";
        status = "Needs navigation";
      } else if (ext === "csv") {
        typeDetected = "Navigation Telemetry CSV";
        status = "Parsed";
      } else {
        typeDetected = "Unsupported Format";
        status = "Unsupported";
      }

      return {
        file: f,
        name: f.name,
        typeDetected,
        sizeFormatted: `${(f.size / (1024 * 1024)).toFixed(2)} MB`,
        status,
      };
    });

    setUploadedFiles((prev) => [...prev, ...newItems]);

    // If user uploaded a raster image, load it into an image element for real pixel processing
    const imgFile = filesArr.find((f) =>
      ["png", "jpg", "jpeg", "tif", "tiff", "webp"].includes(f.name.split(".").pop()?.toLowerCase() || "")
    );
    if (imgFile) {
      const url = URL.createObjectURL(imgFile);
      const img = new Image();
      img.onload = () => {
        setLoadedImageObj(img);
        setLoadedImageUrl(url);
        setImageStats({ width: img.naturalWidth, height: img.naturalHeight });

        // Run real-time acoustic modality verification
        const modality = checkImageModality(img);
        setModalityCheck(modality);

        // If non-SSS, update file table entry status
        if (!modality.isSSS) {
          setUploadedFiles((prev) =>
            prev.map((item) =>
              item.file === imgFile
                ? { ...item, status: "Non-SSS (Optical)", typeDetected: "Optical RGB Image (Non-Sonar)" }
                : item
            )
          );
        }
      };
      img.src = url;

      const cleanName = imgFile.name.replace(/\.[^/.]+$/, "").replace(/[-_]/g, " ");
      setSurveyName(`Survey · ${cleanName}`);
      setAreaLocation("Field Raster Inspection (Uncalibrated)");
    }
  };

  const loadSampleDataset = async () => {
    try {
      const imgRes = await fetch("/samples/1_Sonar_Barge_No1_Crop.png");
      const imgBlob = await imgRes.blob();
      const imgFile = new File([imgBlob], "1_Sonar_Barge_No1_Crop.png", { type: "image/png" });

      const navRes = await fetch("/samples/Chennai_Port_Approach_Nav.csv");
      const navBlob = await navRes.blob();
      const navFile = new File([navBlob], "Chennai_Port_Approach_Nav.csv", { type: "text/csv" });

      setUploadedFiles([]);
      handleFiles([imgFile, navFile]);
      setSurveyName("Survey · Chennai Port Barge Wreck");
      setAreaLocation("Chennai Port Outer Approach (13.085°N, 80.298°E)");
    } catch (err) {
      console.error("Failed to load sample dataset:", err);
      alert("Could not load sample files automatically. Please use 'Browse files' and select from D:\\SIHPS2\\test_samples");
    }
  };

  const handleStartProcessing = async () => {
    setBackendError(null);

    const imgItem = uploadedFiles.find((f) =>
      ["png", "jpg", "jpeg", "tif", "tiff", "webp"].includes(f.file.name.split(".").pop()?.toLowerCase() || "")
    );
    const navItem = uploadedFiles.find((f) => f.file.name.toLowerCase().endsWith(".csv"));

    if (!imgItem) {
      alert("Please upload at least one side-scan sonar raster or native log file.");
      return;
    }

    setIsUploading(true);
    setIsProcessing(true);
    setProcessingProgress(20);

    const surveyId = `SN-2026-${String(surveys.length + 10).padStart(4, "0")}`;

    try {
      // Single Engine: Python backend is the sole source of truth
      const result = await uploadAndAnalyzeSurvey(
        imgItem.file,
        navItem?.file || null,
        surveyId,
        surveyName || imgItem.name,
        0.10
      );

      setProcessingProgress(80);

      if (loadedImageObj && loadedImageUrl) {
        setUploadedImageUrl(loadedImageUrl);
        setUploadedImageElement(loadedImageObj);
      }

      setSurveys((prev) => [result.survey, ...prev.filter((s) => s.id !== result.survey.id)]);
      setCurrentSurvey(result.survey);
      setDetections(result.detections);
      setSelectedDetection(result.detections[0] || null);

      setProcessingProgress(100);
      setIsProcessing(false);
      setIsUploading(false);
      setIsDialogOpen(false);
      setActiveTab("analysis");
    } catch (err: any) {
      setIsProcessing(false);
      setIsUploading(false);
      const msg = err?.message?.includes("offline")
        ? "Analysis backend offline"
        : (err?.message || "Failed to analyze survey");
      setBackendError(msg);
    }
  };

  const handleDelete = (id: string, name: string) => {
    if (confirm(`Confirm deletion of hydrographic survey record:\n${id} — ${name}?`)) {
      setSurveys((prev) => prev.filter((s) => s.id !== id));
    }
  };

  return (
    <div className="p-6 space-y-4 max-w-full overflow-y-auto h-full">
      {/* Top Header & Breadcrumb */}
      <div className="flex items-center justify-between pb-2 border-b border-border">
        <div>
          <div className="text-[12px] font-mono text-text-muted">SURVEYS / REPOSITORY</div>
          <h1 className="text-[20px] font-semibold text-text mt-0.5">Hydrographic Survey Manifests</h1>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={loadSyntheticDemo}
            className="flex items-center gap-1.5 px-3 py-2 bg-surface hover:bg-surface-2 border border-border text-text text-[13px] font-medium rounded transition-colors"
          >
            <Sparkles className="w-4 h-4 text-amber-500" />
            <span>Load demo (synthetic)</span>
          </button>
          <button
            onClick={() => {
              setCurrentStep(1);
              setIsDialogOpen(true);
            }}
            className="flex items-center gap-2 px-3.5 py-2 bg-primary hover:bg-primary-hover text-white text-[13px] font-medium rounded transition-colors"
          >
            <Plus className="w-4 h-4" />
            <span>New survey upload</span>
          </button>
        </div>
      </div>

      {/* Backend Offline / Analysis Error Banner */}
      {backendError && (
        <div className="p-3 bg-danger/10 border border-danger/30 rounded flex items-center justify-between text-[12px] text-danger font-medium">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            <span>Analysis Error: {backendError}. Please check that Python backend is active at http://localhost:8000</span>
          </div>
          <button onClick={() => setBackendError(null)} className="text-text-muted hover:text-text text-[11px] underline">
            Dismiss
          </button>
        </div>
      )}

      {/* Survey List Table */}
      <div className="panel overflow-hidden">
        <div className="px-4 py-2.5 bg-surface-2 border-b border-border flex justify-between items-center">
          <span className="section-label">REGISTERED SURVEY RECORDS ({surveys.length})</span>
          <span className="text-[12px] font-mono text-text-muted">Storage: 100% Local Disk</span>
        </div>
        <div className="overflow-x-auto">
          <table className="hydro-table">
            <thead>
              <tr>
                <th>Survey ID</th>
                <th>Survey Name</th>
                <th>Acquisition Date</th>
                <th>Platform / Vessel</th>
                <th className="numeric">Length (km)</th>
                <th className="numeric">Pings</th>
                <th>Detections</th>
                <th>Geotag Status</th>
                <th>Status</th>
                <th className="text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {surveys.length === 0 ? (
                <tr>
                  <td colSpan={10} className="text-center py-12 text-text-muted">
                    <div className="flex flex-col items-center justify-center gap-2">
                      <div className="text-[14px] font-medium text-text">No registered survey records</div>
                      <p className="text-[12px] text-text-muted max-w-md">
                        Upload raw side-scan sonar files to analyze seabed records, or load synthetic demo data for testing.
                      </p>
                      <div className="flex items-center gap-3 mt-3">
                        <button
                          onClick={() => {
                            setCurrentStep(1);
                            setIsDialogOpen(true);
                          }}
                          className="px-3 py-1.5 bg-primary text-white text-[12px] font-medium rounded hover:bg-primary-hover transition-colors"
                        >
                          New survey upload
                        </button>
                        <button
                          onClick={loadSyntheticDemo}
                          className="px-3 py-1.5 bg-surface hover:bg-surface-2 border border-border text-text text-[12px] font-medium rounded transition-colors"
                        >
                          Load demo (synthetic)
                        </button>
                      </div>
                    </div>
                  </td>
                </tr>
              ) : (
                surveys.map((survey) => (
                  <tr key={survey.id} className="hover:bg-surface-2/50 transition-colors">
                    <td className="font-mono font-medium text-text text-[12px]">{survey.id}</td>
                    <td className="font-medium text-text">
                      <div className="flex items-center gap-1.5 flex-wrap">
                        <span>{survey.name}</span>
                        {(survey.isDemoSynthetic || survey.name.includes("DEMO")) && (
                          <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-mono bg-amber-500/10 text-amber-500 border border-amber-500/30 font-semibold">
                            DEMO — SYNTHETIC DATA
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="font-mono text-[12px] text-text-muted">{survey.date}</td>
                    <td className="text-text-muted">{survey.platform}</td>
                    <td className="numeric">{survey.lineLengthKm.toFixed(2)}</td>
                    <td className="numeric">{survey.pingCount.toLocaleString()}</td>
                    <td>
                      <div className="flex items-center gap-1.5 font-mono text-[12px]">
                        <span className="text-success font-semibold">{survey.verifiedCount} ver</span>
                        <span className="text-text-muted">/</span>
                        <span className="text-text-muted">{survey.suppressedCount} supp</span>
                      </div>
                    </td>
                    <td>
                      <span
                        className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-mono ${
                          survey.geoStatus === "AVAILABLE"
                            ? "bg-success/10 text-success border border-success/30"
                            : "bg-accent/10 text-accent border border-accent/30"
                        }`}
                      >
                        {survey.geoStatus}
                      </span>
                    </td>
                    <td>
                      <span className="inline-flex items-center gap-1 text-[12px] font-medium text-text">
                        <span className="w-1.5 h-1.5 rounded-full bg-success" />
                        {survey.status}
                      </span>
                    </td>
                    <td className="text-right">
                      <div className="flex items-center justify-end gap-1">
                        <button
                          onClick={() => {
                            setCurrentSurvey(survey);
                            setActiveTab("analysis");
                          }}
                          className="px-2 py-1 bg-surface hover:bg-surface-2 border border-border rounded text-[12px] font-medium text-primary hover:text-primary-hover transition-colors"
                        >
                          Open
                        </button>
                        <button
                          onClick={() => {
                            setCurrentSurvey(survey);
                            setActiveTab("reports");
                          }}
                          className="px-2 py-1 bg-surface hover:bg-surface-2 border border-border rounded text-[12px] text-text-muted hover:text-text transition-colors"
                          title="Export Survey"
                        >
                          <Download className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={() => handleDelete(survey.id, survey.name)}
                          className="p-1 hover:bg-danger/10 text-text-muted hover:text-danger rounded border border-transparent hover:border-danger/30 transition-colors"
                          title="Delete Survey"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Upload Dialog Modal (Width: 720px) */}
      {isDialogOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="bg-surface border border-border rounded w-[720px] max-w-full max-h-[90vh] flex flex-col overflow-hidden">
            {/* Dialog Header */}
            <div className="px-5 py-3.5 border-b border-border flex justify-between items-center bg-surface-2">
              <div>
                <div className="section-label">SURVEY INGESTION WIZARD</div>
                <div className="text-[16px] font-semibold text-text">
                  Step {currentStep} of 3:{" "}
                  {currentStep === 1
                    ? "Upload Sonar Logs & Navigation"
                    : currentStep === 2
                    ? "Survey Acquisition Metadata"
                    : "Processing & Physics Options"}
                </div>
              </div>
              <button
                onClick={() => setIsDialogOpen(false)}
                className="text-text-muted hover:text-text p-1 text-[13px] font-mono"
              >
                ✕
              </button>
            </div>

            {/* Stepper Progress Bar */}
            <div className="h-1 bg-surface-2 flex">
              <div
                className="bg-primary transition-all duration-300"
                style={{ width: `${(currentStep / 3) * 100}%` }}
              />
            </div>

            {/* Dialog Body */}
            <div className="p-5 overflow-y-auto flex-1 space-y-4">
              {/* STEP 1: Files */}
              {currentStep === 1 && (
                <div className="space-y-4">
                  {/* Drop zone */}
                  <div
                    onDragOver={(e) => {
                      e.preventDefault();
                      setDragOver(true);
                    }}
                    onDragLeave={() => setDragOver(false)}
                    onDrop={(e) => {
                      e.preventDefault();
                      setDragOver(false);
                      handleFiles(e.dataTransfer.files);
                    }}
                    className={`border-2 border-dashed rounded p-6 text-center transition-colors ${
                      dragOver ? "border-primary bg-primary/5" : "border-border bg-surface-2/40"
                    }`}
                  >
                    <UploadCloud className="w-8 h-8 text-primary mx-auto mb-2" strokeWidth={1.5} />
                    <div className="text-[14px] font-medium text-text">
                      Drag and drop side-scan sonar files here
                    </div>
                    <div className="text-[12px] text-text-muted mt-1">
                      Accepts native sonar logs: <b>.xtf, .jsf</b> · Rasters: <b>.tif, .tiff, .png, .jpg</b> · Navigation: <b>.csv</b>
                    </div>
                    <div className="mt-3">
                      <label className="cursor-pointer inline-flex items-center gap-1.5 px-3 py-1.5 bg-primary text-white text-[13px] font-medium rounded hover:bg-primary-hover transition-colors">
                        <span>Browse files</span>
                        <input
                          type="file"
                          multiple
                          accept=".xtf,.jsf,.tif,.tiff,.png,.jpg,.jpeg,.csv"
                          className="hidden"
                          onChange={(e) => handleFiles(e.target.files)}
                        />
                      </label>
                    </div>
                  </div>

                  {/* Inline Policy Notice */}
                  <div className="p-3 bg-surface-2 border border-border rounded text-[12px] text-text flex items-start gap-2">
                    <AlertCircle className="w-4 h-4 text-accent shrink-0 mt-0.5" strokeWidth={1.5} />
                    <div>
                      <b>Policy Rule:</b> Image-only uploads are processed without geotagging. Coordinates will be reported as <code>UNAVAILABLE</code> — never estimated.
                    </div>
                  </div>

                  {/* Files Table */}
                  <div>
                    <div className="section-label mb-1.5">DETECTED INGESTION FILES ({uploadedFiles.length})</div>
                    {uploadedFiles.length === 0 ? (
                      <div className="p-4 text-center text-text-muted text-[13px] border border-border rounded bg-surface-2/20">
                        No files selected yet. Click "Browse files" or drag .xtf / .jsf logs into the box above.
                      </div>
                    ) : (
                      <div className="panel overflow-hidden">
                        <table className="hydro-table">
                          <thead>
                            <tr>
                              <th>File Name</th>
                              <th>Type Detected</th>
                              <th className="numeric">Size</th>
                              <th>Status</th>
                              <th className="text-right">Action</th>
                            </tr>
                          </thead>
                          <tbody>
                            {uploadedFiles.map((f, idx) => (
                              <tr key={idx}>
                                <td className="font-mono text-[12px] font-medium">{f.name}</td>
                                <td>{f.typeDetected}</td>
                                <td className="numeric font-mono">{f.sizeFormatted}</td>
                                <td>
                                  <span
                                    className={`inline-flex px-1.5 py-0.5 rounded text-[11px] font-mono ${
                                      f.status === "Parsed"
                                        ? "bg-success/10 text-success border border-success/30"
                                        : f.status === "Needs navigation"
                                        ? "bg-accent/10 text-accent border border-accent/30"
                                        : "bg-danger/10 text-danger border border-danger/30"
                                    }`}
                                  >
                                    {f.status}
                                  </span>
                                </td>
                                <td className="text-right">
                                  <button
                                    onClick={() => setUploadedFiles(uploadedFiles.filter((_, i) => i !== idx))}
                                    className="text-text-muted hover:text-danger text-[12px]"
                                  >
                                    ✕
                                  </button>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>

                  {/* Modality Check Verification Card */}
                  {loadedImageUrl && modalityCheck && (
                    !modalityCheck.isSSS ? (
                      <div className="p-3.5 bg-danger/10 border-2 border-danger/40 rounded text-[13px] text-text space-y-2">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2 text-danger font-semibold">
                            <AlertTriangle className="w-4 h-4 shrink-0 text-danger" />
                            <span>SENSOR MODALITY AUDIT FAILED: NON-SSS IMAGE DETECTED</span>
                          </div>
                          <span className="font-mono text-[11px] px-2 py-0.5 rounded bg-danger text-white">
                            Modality: {modalityCheck.detectedModality}
                          </span>
                        </div>
                        <p className="text-[12px] text-text-muted leading-relaxed">
                          {modalityCheck.verdictMessage}
                        </p>
                        <div className="bg-surface/90 p-2.5 rounded border border-border text-[11px] font-mono space-y-0.5">
                          <div className="font-semibold text-text mb-1">Acoustic Sensor QA Diagnostics:</div>
                          {modalityCheck.diagnosticDetails.map((diag, i) => (
                            <div key={i} className="text-text-muted">· {diag}</div>
                          ))}
                        </div>
                        <div className="flex items-center justify-between pt-1">
                          <span className="text-[11px] text-danger font-medium">
                            ⚠️ Warning: Acoustic slant-range, nadir geometry, and shadow-height formulas will be vetoed.
                          </span>
                          <button
                            type="button"
                            onClick={() => {
                              setUploadedFiles([]);
                              setLoadedImageObj(null);
                              setLoadedImageUrl(null);
                              setImageStats(null);
                              setModalityCheck(null);
                              setSurveyName("");
                            }}
                            className="px-2.5 py-1 text-[11px] font-medium bg-danger hover:bg-danger/90 text-white rounded transition-colors"
                          >
                            Remove Non-SSS File
                          </button>
                        </div>
                      </div>
                    ) : (
                      <div className="p-3 bg-surface-2 border border-border rounded flex items-center gap-3">
                        <img
                          src={loadedImageUrl}
                          alt="Uploaded Sonar Preview"
                          className="w-20 h-14 object-cover rounded border border-border bg-black"
                        />
                        <div className="text-[12px] space-y-0.5">
                          <div className="flex items-center gap-2">
                            <span className="font-semibold text-text">Side-Scan Sonar (SSS) Modality Verified</span>
                            <span className="px-1.5 py-0.2 rounded text-[10px] font-mono bg-success/10 text-success border border-success/30">
                              {modalityCheck.confidencePct}% SSS Parity
                            </span>
                          </div>
                          <div className="font-mono text-text-muted">
                            Resolution: {imageStats?.width} across-track samples × {imageStats?.height} pings
                          </div>
                          <div className="text-success text-[11px] font-mono">
                            ✓ Monochromatic acoustic backscatter confirmed · Ready for CFAR highlight-shadow decomposition
                          </div>
                        </div>
                      </div>
                    )
                  )}
                </div>
              )}

              {/* STEP 2: Survey Details Form */}
              {currentStep === 2 && (
                <div className="grid grid-cols-2 gap-4 text-[13px]">
                  {imageStats && (
                    <div className="col-span-2 p-2.5 bg-primary/5 border border-primary/20 rounded text-[12px] font-mono text-text flex items-center justify-between">
                      <span>SOURCE GEOMETRY: {imageStats.width} SAMPLES × {imageStats.height} PINGS</span>
                      <span className="text-primary font-semibold">IMAGE-BASED PING RECONSTRUCTION</span>
                    </div>
                  )}
                  <div className="space-y-1">
                    <label className="font-medium text-text">Survey Name *</label>
                    <input
                      type="text"
                      value={surveyName}
                      onChange={(e) => setSurveyName(e.target.value)}
                      className="w-full px-2.5 py-1.5 border border-border rounded bg-surface text-text focus:outline-none focus:border-primary font-mono text-[13px]"
                      placeholder="e.g. Chennai Coast Line 09"
                    />
                  </div>

                  <div className="space-y-1">
                    <label className="font-medium text-text">Vessel / Platform</label>
                    <input
                      type="text"
                      value={vessel}
                      onChange={(e) => setVessel(e.target.value)}
                      className="w-full px-2.5 py-1.5 border border-border rounded bg-surface text-text focus:outline-none focus:border-primary text-[13px]"
                    />
                  </div>

                  <div className="space-y-1">
                    <label className="font-medium text-text">Sonar Model</label>
                    <select
                      value={sonarModel}
                      onChange={(e) => setSonarModel(e.target.value)}
                      className="w-full px-2.5 py-1.5 border border-border rounded bg-surface text-text focus:outline-none focus:border-primary text-[13px]"
                    >
                      <option value="EdgeTech 4125">EdgeTech 4125</option>
                      <option value="EdgeTech 4200">EdgeTech 4200</option>
                      <option value="Klein 3000">Klein 3000</option>
                      <option value="Kongsberg PULSar">Kongsberg PULSar</option>
                      <option value="Other">Other Hydrographic SSS</option>
                    </select>
                  </div>

                  <div className="space-y-1">
                    <label className="font-medium text-text">Frequency (kHz)</label>
                    <select
                      value={frequency}
                      onChange={(e) => setFrequency(e.target.value)}
                      className="w-full px-2.5 py-1.5 border border-border rounded bg-surface text-text focus:outline-none focus:border-primary text-[13px]"
                    >
                      <option value="100">100 kHz (Low Frequency / Search)</option>
                      <option value="400">400 kHz (High Resolution)</option>
                      <option value="600">600 kHz (Ultra High Resolution)</option>
                      <option value="900">900 kHz (Inspection)</option>
                      <option value="Other">Other</option>
                    </select>
                  </div>

                  <div className="space-y-1">
                    <label className="font-medium text-text">Range per side (m)</label>
                    <input
                      type="number"
                      value={rangeM}
                      onChange={(e) => setRangeM(e.target.value)}
                      className="w-full px-2.5 py-1.5 border border-border rounded bg-surface text-text focus:outline-none focus:border-primary font-mono text-[13px]"
                    />
                  </div>

                  <div className="space-y-1">
                    <label className="font-medium text-text">Towfish altitude (m) (auto if telemetry)</label>
                    <input
                      type="number"
                      value={altitudeM}
                      onChange={(e) => setAltitudeM(e.target.value)}
                      className="w-full px-2.5 py-1.5 border border-border rounded bg-surface text-text focus:outline-none focus:border-primary font-mono text-[13px]"
                    />
                  </div>

                  <div className="space-y-1">
                    <label className="font-medium text-text">Area / Location</label>
                    <input
                      type="text"
                      value={areaLocation}
                      onChange={(e) => setAreaLocation(e.target.value)}
                      className="w-full px-2.5 py-1.5 border border-border rounded bg-surface text-text focus:outline-none focus:border-primary text-[13px]"
                    />
                  </div>

                  <div className="space-y-1">
                    <label className="font-medium text-text">Acquisition Date</label>
                    <input
                      type="date"
                      value={date}
                      onChange={(e) => setDate(e.target.value)}
                      className="w-full px-2.5 py-1.5 border border-border rounded bg-surface text-text focus:outline-none focus:border-primary text-[13px]"
                    />
                  </div>

                  <div className="space-y-1">
                    <label className="font-medium text-text">Operator</label>
                    <input
                      type="text"
                      value={operator}
                      onChange={(e) => setOperator(e.target.value)}
                      className="w-full px-2.5 py-1.5 border border-border rounded bg-surface text-text focus:outline-none focus:border-primary text-[13px]"
                    />
                  </div>

                  <div className="space-y-1">
                    <label className="font-medium text-text">Region for UTM zone (Auto-detected)</label>
                    <input
                      type="text"
                      readOnly
                      value={utmZone}
                      className="w-full px-2.5 py-1.5 border border-border rounded bg-surface-2 text-text-muted font-mono text-[12px] cursor-not-allowed"
                    />
                  </div>
                </div>
              )}

              {/* STEP 3: Processing Options */}
              {currentStep === 3 && (
                <div className="space-y-4 text-[13px]">
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-1">
                      <label className="font-medium text-text">Despeckle Filter</label>
                      <select
                        value={despeckle}
                        onChange={(e) => setDespeckle(e.target.value as any)}
                        className="w-full px-2.5 py-1.5 border border-border rounded bg-surface text-text text-[13px]"
                      >
                        <option value="Lee">Lee Filter (Edge-preserving)</option>
                        <option value="Frost">Frost Filter (Multiplicative noise)</option>
                        <option value="None">None (Raw intensity)</option>
                      </select>
                    </div>

                    <div className="space-y-1">
                      <label className="font-medium text-text">Motion-mask roll/pitch threshold</label>
                      <div className="flex items-center gap-2">
                        <input
                          type="number"
                          value={motionThreshold}
                          onChange={(e) => setMotionThreshold(e.target.value)}
                          className="w-24 px-2.5 py-1.5 border border-border rounded bg-surface text-text font-mono text-[13px]"
                        />
                        <span className="text-text-muted font-mono">degrees (default: 5°)</span>
                      </div>
                    </div>

                    <div className="space-y-1">
                      <label className="font-medium text-text">Tile Size</label>
                      <input
                        type="number"
                        value={tileSize}
                        readOnly
                        className="w-full px-2.5 py-1.5 border border-border rounded bg-surface-2 text-text font-mono text-[13px] cursor-not-allowed"
                      />
                    </div>

                    <div className="space-y-1">
                      <label className="font-medium text-text">Multi-pass matching radius</label>
                      <div className="flex items-center gap-2">
                        <input
                          type="number"
                          value={matchingRadius}
                          onChange={(e) => setMatchingRadius(e.target.value)}
                          className="w-24 px-2.5 py-1.5 border border-border rounded bg-surface text-text font-mono text-[13px]"
                        />
                        <span className="text-text-muted font-mono">meters (default: 5 m)</span>
                      </div>
                    </div>
                  </div>

                  <div className="p-3 bg-surface-2 border border-border rounded space-y-3">
                    <div className="flex items-center justify-between">
                      <div>
                        <div className="font-medium text-text">Confidence threshold slider</div>
                        <div className="text-[12px] text-text-muted">Minimum confidence to report anomaly</div>
                      </div>
                      <div className="flex items-center gap-3">
                        <input
                          type="range"
                          min="0.20"
                          max="0.80"
                          step="0.05"
                          value={confThreshold}
                          onChange={(e) => setConfThreshold(e.target.value)}
                          className="w-32 cursor-pointer"
                        />
                        <span className="font-mono font-semibold text-text text-[13px] w-12 text-right">
                          {Number(confThreshold).toFixed(2)}
                        </span>
                      </div>
                    </div>

                    <div className="h-px bg-border" />

                    <div className="flex items-center justify-between">
                      <div>
                        <div className="font-medium text-text">Show suppressed detections</div>
                        <div className="text-[12px] text-text-muted">Display items vetoed by physics filters</div>
                      </div>
                      <input
                        type="checkbox"
                        checked={showSuppressed}
                        onChange={(e) => setShowSuppressed(e.target.checked)}
                        className="w-4 h-4 cursor-pointer accent-primary"
                      />
                    </div>

                    <div className="h-px bg-border" />

                    <div className="space-y-1">
                      <label className="font-medium text-text">Deployment profile</label>
                      <div className="flex gap-4 mt-1">
                        <label className="flex items-center gap-2 cursor-pointer">
                          <input
                            type="radio"
                            name="profile"
                            checked={deploymentProfile === "Shore FP32"}
                            onChange={() => setDeploymentProfile("Shore FP32")}
                            className="accent-primary"
                          />
                          <span>Shore FP32 (Full Multi-view)</span>
                        </label>
                        <label className="flex items-center gap-2 cursor-pointer">
                          <input
                            type="radio"
                            name="profile"
                            checked={deploymentProfile === "Onboard INT8 (Jetson Orin Nano)"}
                            onChange={() => setDeploymentProfile("Onboard INT8 (Jetson Orin Nano)")}
                            className="accent-primary"
                          />
                          <span>Onboard INT8 (Jetson Orin Nano)</span>
                        </label>
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Dialog Footer */}
            <div className="px-5 py-3 border-t border-border flex justify-between items-center bg-surface-2">
              <button
                type="button"
                onClick={() => setIsDialogOpen(false)}
                className="px-3 py-1.5 border border-border bg-surface hover:bg-surface-2 text-text text-[13px] rounded transition-colors"
              >
                Cancel
              </button>

              <div className="flex gap-2">
                {currentStep > 1 && (
                  <button
                    type="button"
                    onClick={() => setCurrentStep((prev) => (prev - 1) as any)}
                    className="px-3 py-1.5 border border-border bg-surface hover:bg-surface-2 text-text text-[13px] rounded transition-colors"
                  >
                    Back
                  </button>
                )}
                {currentStep < 3 ? (
                  <button
                    type="button"
                    onClick={() => setCurrentStep((prev) => (prev + 1) as any)}
                    className="px-4 py-1.5 bg-primary hover:bg-primary-hover text-white text-[13px] font-medium rounded transition-colors"
                  >
                    Next Step
                  </button>
                ) : (
                  <button
                    type="button"
                    disabled={isUploading}
                    onClick={handleStartProcessing}
                    className="px-4 py-1.5 bg-primary hover:bg-primary-hover disabled:opacity-50 text-white text-[13px] font-medium rounded transition-colors flex items-center gap-1.5"
                  >
                    {isUploading ? (
                      <>
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        <span>Analyzing with Python Engine...</span>
                      </>
                    ) : (
                      <>
                        <Play className="w-3.5 h-3.5 fill-current" />
                        <span>Start Processing</span>
                      </>
                    )}
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
