import { z } from "zod";

export const BoundingBoxPxSchema = z.object({
  row_min: z.number().int().nonnegative(),
  col_min: z.number().int().nonnegative(),
  row_max: z.number().int().nonnegative(),
  col_max: z.number().int().nonnegative(),
});
export type BoundingBoxPx = z.infer<typeof BoundingBoxPxSchema>;

export const DimensionsSchema = z.object({
  length_px: z.number().nonnegative(),
  width_px: z.number().nonnegative(),
  length_m: z.number().nonnegative().nullable().optional(),
  width_m: z.number().nonnegative().nullable().optional(),
});
export type Dimensions = z.infer<typeof DimensionsSchema>;

export const UTMCoordinatesSchema = z.object({
  easting: z.number(),
  northing: z.number(),
  zone: z.number().int(),
  hemisphere: z.string(),
});
export type UTMCoordinates = z.infer<typeof UTMCoordinatesSchema>;

export const GeoPositionSchema = z.object({
  status: z.enum(["AVAILABLE", "UNAVAILABLE"]),
  lat: z.number().nullable().optional(),
  lon: z.number().nullable().optional(),
  utm: UTMCoordinatesSchema.nullable().optional(),
  source: z.string().nullable().optional(),
});
export type GeoPosition = z.infer<typeof GeoPositionSchema>;

export const PipelineStageSchema = z.object({
  step: z.number().int(),
  name: z.string(),
  status: z.string(),
  duration_ms: z.number(),
  details: z.string().nullable().optional(),
});
export type PipelineStage = z.infer<typeof PipelineStageSchema>;

export const RawCandidateSchema = z.object({
  id: z.string(),
  source: z.string(),
  bbox_px: BoundingBoxPxSchema,
  raw_score: z.number(),
  raw_class: z.string(),
  has_shadow: z.boolean(),
  snr_db: z.number(),
});
export type RawCandidate = z.infer<typeof RawCandidateSchema>;

export const TargetEvidenceSchema = z.object({
  cnn_score: z.number(),
  shc_score: z.number(),
  height_estimate_m: z.number().nullable().optional(),
  shadow_side: z.string(),
  regularity_score: z.number(),
  is_sand_ripple: z.boolean(),
  motion_penalty: z.number(),
  persistence_score: z.number(),
  pass_count: z.number().int(),
  fused_confidence: z.number(),
  suppressed: z.boolean(),
  suppression_reason: z.string().nullable().optional(),
  s_net: z.number().nullable().optional(),
  annular_contrast: z.number().nullable().optional(),
  anomaly_score: z.number().nullable().optional(),
  anthropogenic_score: z.number().nullable().optional(),
});
export type TargetEvidence = z.infer<typeof TargetEvidenceSchema>;

export const TargetOutputSchema = z.object({
  id: z.string(),
  class_name: z.string(),
  confidence: z.number(),
  decision: z.string(),
  decision_reason: z.string(),
  evidence: TargetEvidenceSchema,
  bbox_px: BoundingBoxPxSchema,
  dims: DimensionsSchema,
  geo: GeoPositionSchema,
  height_m: z.number().nullable().optional(),
  quality_overlap_pct: z.number(),
  raw_candidate_source: z.string(),
  merged_count: z.number().int().default(1),
});
export type TargetOutput = z.infer<typeof TargetOutputSchema>;

export const SummaryCountsSchema = z.object({
  total_candidates: z.number().int().nonnegative(),
  verified_count: z.number().int().nonnegative(),
  suppressed_count: z.number().int().nonnegative(),
  uncertain_count: z.number().int().nonnegative(),
  by_class: z.record(z.string(), z.number().int()).default({}),
});
export type SummaryCounts = z.infer<typeof SummaryCountsSchema>;

export const AnalyzeSurveyInfoSchema = z.object({
  id: z.string(),
  name: z.string(),
  source_file: z.string(),
  swath_range_m: z.number(),
  altitude_m: z.number().nullable().optional(),
  has_nav: z.boolean().default(false),
  created_at: z.string(),
});
export type AnalyzeSurveyInfo = z.infer<typeof AnalyzeSurveyInfoSchema>;

export const AnalyzeResponseSchema = z.object({
  status: z.enum(["ANALYSIS_COMPLETE", "INVALID_INPUT", "ERROR"]),
  survey: AnalyzeSurveyInfoSchema,
  stages: z.array(PipelineStageSchema).default([]),
  raw_candidates: z.array(RawCandidateSchema).default([]),
  targets: z.array(TargetOutputSchema).default([]),
  summary: SummaryCountsSchema,
  detector_status: z.string().default("NOT_TRAINED"),
  calibration_status: z.string().default("uncalibrated"),
  geo_status: z.string().default("UNAVAILABLE"),
  warnings: z.array(z.string()).default([]),
  modality: z.record(z.string(), z.any()).nullable().optional(),
  overlay_url: z.string().nullable().optional(),
  image_shape: z.tuple([z.number(), z.number()]).nullable().optional(),
  error: z.string().nullable().optional(),
  message: z.string().nullable().optional(),
});
export type AnalyzeResponse = z.infer<typeof AnalyzeResponseSchema>;
