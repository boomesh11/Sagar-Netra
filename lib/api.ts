import { Survey, Detection, DebrisClass } from "@/types/survey";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export class BackendOfflineError extends Error {
  constructor(message = "Analysis backend offline") {
    super(message);
    this.name = "BackendOfflineError";
  }
}

/**
 * Checks connectivity with the SagarNetra Python FastAPI engine.
 */
export async function checkBackendHealth(): Promise<{ online: boolean; version?: string; device?: string }> {
  try {
    const res = await fetch(`${API_BASE}/api/health`, { method: "GET", cache: "no-store" });
    if (!res.ok) return { online: false };
    const data = await res.json();
    return { online: data.status === "HEALTHY", version: data.version, device: data.device };
  } catch {
    return { online: false };
  }
}

/**
 * Maps a backend SQLite survey record into the frontend Survey interface.
 */
/**
 * Maps a backend SQLite survey record or pipeline response into the frontend Survey interface.
 */
export function mapBackendSurvey(s: any): Survey {
  const isAvailable =
    s.geo_status === "AVAILABLE" ||
    s.geoStatus === "AVAILABLE" ||
    (s.total_targets > 0 && s.confirmed_count > 0);
  const surveyId = s.survey_id || s.id || `SRV_${Date.now()}`;
  const surveyName = s.site_name || s.name || surveyId;
  const verifiedCount =
    s.confirmed_count ??
    s.verifiedCount ??
    s.target_count ??
    s.summary?.verified_count ??
    0;
  const suppressedCount =
    s.confuser_count ??
    s.suppressedCount ??
    s.summary?.suppressed_count ??
    0;
  const pingCount = s.total_pings ?? s.pingCount ?? 500;
  const swathRangeM = s.swath_range_m ?? s.swathRangeM ?? s.rangeM ?? 75.0;

  return {
    id: surveyId,
    name: surveyName,
    date: (s.created_at || s.date || new Date().toISOString()).slice(0, 10),
    platform: s.source_type === "REAL" ? "Hydrographic Survey Vessel" : "Synthetic Acoustic Bench",
    sonarModel: "Dual-Swath SSS",
    frequencyKhz: 450,
    rangeM: swathRangeM,
    altitudeM: s.altitude_m ?? s.altitudeM ?? 8.0,
    lineLengthKm: Number(((pingCount * 0.1) / 1000).toFixed(2)),
    pingCount: pingCount,
    geoStatus: s.geo_status === "UNAVAILABLE" ? "UNAVAILABLE" : (isAvailable ? "AVAILABLE" : "UNAVAILABLE"),
    status: "PROCESSED",
    verifiedCount: verifiedCount,
    suppressedCount: suppressedCount,
    coverageKm2: Number((((pingCount * 0.1 * (swathRangeM * 2)) / 1000000)).toFixed(3)),
    operator: "NIOT Survey Team",
    areaLocation: s.site_name || s.name || "Shelf Survey Area",
    utmZone: "44N",
  };
}

/**
 * Maps a backend detection record into the frontend Detection interface.
 */
export function mapBackendDetection(d: any): Detection {
  const comp = d.components || d.evidence || {};
  const rules = d.rules || [];
  const decisionRule = rules[0] || {};
  const isAvailable =
    (d.position_status === "AVAILABLE" || d.geo?.status === "AVAILABLE") &&
    (d.lat ?? d.geo?.lat) !== null &&
    (d.lon ?? d.geo?.lon) !== null;
  const isSuppressed =
    d.status === "REJECTED" ||
    d.decision === "natural_suppressed" ||
    d.class_name === "natural_suppressed" ||
    d.class_name === "natural_feature" ||
    Boolean(d.evidence?.suppressed);

  const rawCls = d.class_name || d.class || "unknown_manmade";
  const validClasses: DebrisClass[] = [
    "wreck", "pipe_cylinder", "net_debris", "other_manmade",
    "unknown_manmade", "natural_suppressed", "uncertain", "invalid_input"
  ];
  const assignedClass: DebrisClass = validClasses.includes(rawCls as DebrisClass)
    ? (rawCls as DebrisClass)
    : "unknown_manmade";

  const latVal = d.lat ?? d.geo?.lat ?? null;
  const lonVal = d.lon ?? d.geo?.lon ?? null;
  const widthVal = d.dims?.width_m ?? d.width_m ?? null;
  const lengthVal = d.dims?.length_m ?? d.length_m ?? null;
  const r95Val = d.r95_m ?? 2.45;

  return {
    id: d.target_id || d.id || `TGT_${Date.now()}`,
    surveyId: d.survey_id || d.surveyId || "SRV_UNKNOWN",
    class: assignedClass,
    rawClass: "unknown_manmade",
    confidence: Number(d.hazard_confidence ?? d.confidence) || 0,
    rawConfidence: Math.min(100, Math.round((comp.p_cal ?? comp.cnn_score ?? 0.8) * 100)),
    evidence: {
      cnn: Number(comp.p_cal ?? comp.cnn_score ?? 0.8),
      shc: Number(comp.v_phys ?? comp.shc_score ?? 0.8),
      regularity: Number(comp.regularity_score ?? 0.7),
      motionPenalty: Number(comp.motion_penalty ?? 0.0),
      persistence: Number(comp.persistence_score ?? 0.5),
    },
    decisionReason: d.decision_reason || decisionRule.reason || (isSuppressed ? "Acoustic physics veto" : "Physics confirmed candidate"),
    heightEstimateM: d.height_m ?? comp.height_estimate_m ?? null,
    shadowSide: (comp.shadow_side === "incorrect" ? "incorrect" : "correct") as any,
    bbox: {
      pingStart: d.bbox_px?.row_min ?? 100,
      pingEnd: d.bbox_px?.row_max ?? 160,
      rangeStartPx: d.bbox_px?.col_min ?? 200,
      rangeEndPx: d.bbox_px?.col_max ?? 280,
    },
    geo: {
      lat: isAvailable && latVal !== null ? Number(latVal) : null,
      lon: isAvailable && lonVal !== null ? Number(lonVal) : null,
      widthM: widthVal,
      lengthM: lengthVal,
      r95M: isAvailable ? r95Val : null,
      status: isAvailable ? "AVAILABLE" : "UNAVAILABLE",
    },
    widthM: widthVal ?? undefined,
    lengthM: lengthVal ?? undefined,
    r95M: isAvailable ? r95Val : null,
    diverSearchBoxM: isAvailable ? { width: r95Val * 2, height: r95Val * 2 } : undefined,
    passes: ["LINE_01"],
    suppressed: isSuppressed,
    suppressionReason: isSuppressed ? (d.decision_reason || decisionRule.reason || "Suppressed by EchoSift") : null,
    operatorReview: d.review_status && d.review_status !== "UNREVIEWED" ? (d.review_status as any) : undefined,
  };
}

/**
 * Fetches all surveys from the backend SQLite database.
 */
export async function fetchSurveys(): Promise<Survey[]> {
  try {
    const res = await fetch(`${API_BASE}/api/surveys`, { cache: "no-store" });
    if (!res.ok) {
      throw new BackendOfflineError(`Backend returned ${res.status}: ${res.statusText}`);
    }
    const rawList = await res.json();
    return rawList.map(mapBackendSurvey);
  } catch (err: any) {
    if (err instanceof BackendOfflineError) throw err;
    throw new BackendOfflineError("Analysis backend offline");
  }
}

/**
 * Fetches survey summary by ID.
 */
export async function fetchSurveyById(surveyId: string): Promise<Survey | null> {
  try {
    const res = await fetch(`${API_BASE}/api/surveys/${surveyId}`, { cache: "no-store" });
    if (!res.ok) {
      if (res.status === 404) return null;
      throw new BackendOfflineError();
    }
    const raw = await res.json();
    return mapBackendSurvey(raw);
  } catch (err: any) {
    if (err instanceof BackendOfflineError) throw err;
    throw new BackendOfflineError("Analysis backend offline");
  }
}

/**
 * Fetches detections for a given survey from the backend.
 */
export async function fetchDetections(surveyId: string, physicsVerified = true): Promise<Detection[]> {
  try {
    const res = await fetch(`${API_BASE}/api/surveys/${surveyId}/detections`, { cache: "no-store" });
    if (!res.ok) {
      throw new BackendOfflineError();
    }
    const rawList = await res.json();
    const detections = rawList.map(mapBackendDetection);

    if (physicsVerified) {
      return detections;
    } else {
      return detections.map((d: Detection) => ({
        ...d,
        confidence: d.rawConfidence,
        suppressed: false,
        suppressionReason: null,
      }));
    }
  } catch (err: any) {
    if (err instanceof BackendOfflineError) throw err;
    throw new BackendOfflineError("Analysis backend offline");
  }
}

/**
 * Submits an image (+ optional navigation CSV) to the single Python analysis backend.
 * Never falls back to fake results if the backend is down.
 */
export async function uploadAndAnalyzeSurvey(
  imageFile: File,
  navFile?: File | null,
  surveyId?: string,
  siteName?: string,
  groundRes = 0.10
): Promise<{ survey: Survey; detections: Detection[]; report: any }> {
  const formData = new FormData();
  formData.append("image", imageFile);
  if (navFile) {
    formData.append("nav", navFile);
  }
  if (surveyId) {
    formData.append("survey_id", surveyId);
  }
  if (siteName) {
    formData.append("site_name", siteName);
  }
  formData.append("ground_res", String(groundRes));

  let res: Response;
  try {
    res = await fetch(`${API_BASE}/api/analyze`, {
      method: "POST",
      body: formData,
    });
  } catch {
    throw new BackendOfflineError("Analysis backend offline");
  }

  if (!res.ok) {
    const errText = await res.text().catch(() => "");
    throw new Error(`Analysis failed (${res.status}): ${errText || res.statusText}`);
  }

  const payload = await res.json();

  if (payload.status === "INVALID_INPUT") {
    const emptySurvey: Survey = {
      id: surveyId || `SRV_${Date.now()}`,
      name: siteName || imageFile.name,
      date: new Date().toISOString().slice(0, 10),
      platform: "Optical Non-Sonar",
      sonarModel: "Optical RGB Camera",
      frequencyKhz: 0,
      rangeM: 0,
      altitudeM: 0,
      lineLengthKm: 0,
      pingCount: 0,
      geoStatus: "UNAVAILABLE",
      status: "PROCESSED",
      verifiedCount: 0,
      suppressedCount: 0,
      coverageKm2: 0,
      operator: "Operator",
      areaLocation: "Invalid Input",
      utmZone: "44N",
      modalityStatus: "NON_SSS_DETECTED",
      modalityConfidence: payload.modality?.confidence_pct || 90,
      modalityReason: payload.modality?.verdict_message || "Non-SSS optical image rejected.",
    };
    return {
      survey: emptySurvey,
      detections: [],
      report: payload,
    };
  }

  const survey = mapBackendSurvey({
    ...(payload.survey || {}),
    survey_id: payload.survey?.id || payload.survey_id || surveyId,
    site_name: payload.survey?.name || siteName || imageFile.name,
    total_pings: payload.image_shape ? payload.image_shape[0] : (payload.input?.file_size_bytes ? 512 : 512),
    confirmed_count: payload.summary?.verified_count ?? payload.target_count ?? (payload.detections || []).length,
    confuser_count: payload.summary?.suppressed_count ?? 0,
    swath_range_m: payload.survey?.swath_range_m || 75.0,
    altitude_m: payload.survey?.altitude_m || 12.0,
    geo_status: payload.mode === "IMAGE_ONLY" ? "UNAVAILABLE" : (payload.geo_status || "AVAILABLE"),
  });

  const rawDets = payload.detections || payload.targets || [];
  const detections = rawDets.map(mapBackendDetection);

  return {
    survey,
    detections,
    report: payload,
  };
}

/**
 * Returns backend report export URL.
 */
export function getExportUrl(surveyId: string, format: "json" | "csv" | "geojson" | "kml" | "pdf"): string {
  return `${API_BASE}/api/surveys/${surveyId}/export?format=${format}`;
}

/**
 * Downloads a report format directly from the backend API.
 */
export async function downloadReportFile(surveyId: string, format: "json" | "csv" | "geojson" | "kml" | "pdf"): Promise<void> {
  const url = getExportUrl(surveyId, format);
  try {
    const res = await fetch(url);
    if (!res.ok) {
      throw new BackendOfflineError(`Export request failed with status ${res.status}`);
    }
    const blob = await res.blob();
    const blobUrl = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = blobUrl;
    a.download = `sagarnetra_${surveyId}.${format === "geojson" ? "geojson" : format}`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(blobUrl);
  } catch (err: any) {
    if (err instanceof BackendOfflineError) throw err;
    throw new BackendOfflineError("Analysis backend offline");
  }
}

/**
 * Submits an operator review to the backend.
 */
export async function submitDetectionReview(
  detectionId: string,
  action: "CONFIRMED" | "REJECTED" | "CHANGED_CLASS" | "UNSURE",
  newClass?: string,
  notes?: string
): Promise<{ success: boolean; target_id: string; action: string }> {
  try {
    const res = await fetch(`${API_BASE}/api/review`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ target_id: detectionId, action, new_class: newClass, notes }),
    });
    if (!res.ok) throw new BackendOfflineError();
    const data = await res.json();
    return { success: true, target_id: data.target_id, action: data.action };
  } catch {
    throw new BackendOfflineError("Analysis backend offline");
  }
}

export async function fetchTelemetryData(surveyId: string) {
  return [];
}

export async function addSurvey(survey: Partial<Survey>): Promise<Survey> {
  const mapped = mapBackendSurvey({
    survey_id: survey.id || `SRV_${Date.now()}`,
    site_name: survey.name,
    total_pings: survey.pingCount || 500,
    swath_range_m: survey.rangeM || 75.0,
    altitude_m: survey.altitudeM || 8.0,
    geo_status: survey.geoStatus || "UNAVAILABLE",
    confirmed_count: survey.verifiedCount || 0,
    confuser_count: survey.suppressedCount || 0,
  });
  return mapped;
}
