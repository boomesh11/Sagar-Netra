// Target taxonomy per SIH 2026 PS-26057 brief.
// Trained known classes: wreck | pipe_cylinder | net_debris | other_manmade
// Decision outputs also include: unknown_manmade | natural_suppressed | uncertain | invalid_input
// NOTE: submerged_bicycle, trap_pot, ghost_net are NOT output classes.
//   Bicycle/ladder/cage are open-set held-out test objects → other_manmade or unknown_manmade.
export type DebrisClass =
  | 'wreck'
  | 'pipe_cylinder'
  | 'net_debris'
  | 'other_manmade'
  | 'unknown_manmade'
  | 'natural_suppressed'
  | 'uncertain'
  | 'invalid_input'
  | 'ghost_net'
  | 'wreck_debris'
  | 'trap_pot'
  | 'submerged_bicycle';

export interface BoundingBox {
  pingStart: number;
  pingEnd: number;
  rangeStartPx: number;
  rangeEndPx: number;
}

export interface GeoLocation {
  lat: number | null;
  lon: number | null;
  widthM: number | null;
  lengthM: number | null;
  r95M?: number | null;
  status: 'AVAILABLE' | 'UNAVAILABLE';
}

export interface EvidenceCard {
  cnn: number;           // [0, 1]
  shc: number;           // [0, 1]
  regularity: number;    // [0, 1]
  motionPenalty: number; // [0, 1]
  persistence: number;   // [0, 1]
}

export interface ComprehensiveEvidence {
  cnn: number;
  shadow: number;
  height: number;
  circular: number;
  truss: number;
  tubular: number;
  linear: number;
  mesh: number;
  rope: number;
  draping: number;
  floatSinker: number;
  wreckStructure: number;
  anthropogenic: number;
  anomaly: number;
  motionQuality: number;
  persistence: number;
  naturalSeabed: number;
  structuralMerge: number;
}

export interface ClassEvidenceScores {
  net_debris?: number;
  wreck?: number;
  pipe_cylinder?: number;
  other_manmade?: number;
  unknown_manmade?: number;
  [key: string]: number | undefined;
}

export interface Detection {
  id: string;
  surveyId: string;
  class: DebrisClass;
  rawClass?: DebrisClass;
  confidence: number;    // [0, 100]%
  rawConfidence: number; // [0, 100]%
  evidence: EvidenceCard;
  comprehensiveEvidence?: ComprehensiveEvidence;
  classScores?: ClassEvidenceScores;
  decisionReason?: string;
  overrideOccurred?: boolean;
  overrideLog?: string;
  heightEstimateM: number | null;
  shadowSide: 'correct' | 'incorrect' | 'absent';
  bbox: BoundingBox;
  geo: GeoLocation;
  widthM?: number;
  lengthM?: number;
  r95M?: number | null;
  diverSearchBoxM?: { width: number; height: number };
  mergedComponentsCount?: number;
  passes: string[];
  suppressed: boolean;
  suppressionReason: string | null;
  operatorReview?: 'PENDING' | 'ACCEPTED' | 'REJECTED' | 'SECOND_LOOK';
}

export interface ProcessingStep {
  id: number;
  name: string;
  durationMs: number;
  status: 'pending' | 'running' | 'completed' | 'failed';
  log: string;
}

export interface Survey {
  id: string;
  name: string;
  date: string;
  platform: string;
  sonarModel: string;
  frequencyKhz: number;
  rangeM: number;
  altitudeM: number;
  lineLengthKm: number;
  pingCount: number;
  geoStatus: 'AVAILABLE' | 'UNAVAILABLE';
  status: 'PROCESSED' | 'PROCESSING' | 'READY';
  verifiedCount: number;
  suppressedCount: number;
  coverageKm2: number;
  operator: string;
  areaLocation: string;
  utmZone: string;
  modalityStatus?: 'SSS_VALID' | 'NON_SSS_DETECTED';
  modalityConfidence?: number;
  modalityReason?: string;
  isDemoSynthetic?: boolean;
  dataNote?: string;
}
