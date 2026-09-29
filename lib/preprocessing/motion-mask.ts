/**
 * SagarNetra - Sonar Data-Quality & Motion Mask Analysis
 * 
 * Computes per-ping and spatial motion masks using:
 * - Dynamic attitude thresholds (Roll/Pitch default 5.0 deg, configurable)
 * - Ping-to-ping cross-correlation collapse
 * - Acoustic dropout / stripe detection
 * - Intensity saturation / clipping
 */

export interface MotionConfig {
  maxRollDeg: number;       // Default: 5.0 deg
  maxPitchDeg: number;      // Default: 5.0 deg
  minCorrelation: number;   // Default: 0.40
  dropoutThreshold: number; // Mean intensity below which ping is a dropout
  saturationThreshold: number; // Fraction of clipped samples
}

export const DEFAULT_MOTION_CONFIG: MotionConfig = {
  maxRollDeg: 5.0,
  maxPitchDeg: 5.0,
  minCorrelation: 0.40,
  dropoutThreshold: 8.0,
  saturationThreshold: 0.15,
};

export interface PingQualityResult {
  pingIndex: number;
  qualityScore: number;     // [0, 1] 1 = pristine, 0 = corrupted
  isMotionCorrupted: boolean;
  isDropout: boolean;
  isSaturated: boolean;
  reasons: string[];
}

/**
 * Calculates Pearson correlation coefficient between two consecutive pings.
 */
export function pingCorrelation(p1: number[] | Float32Array, p2: number[] | Float32Array): number {
  const n = Math.min(p1.length, p2.length);
  if (n === 0) return 1.0;

  let sum1 = 0, sum2 = 0;
  for (let i = 0; i < n; i++) {
    sum1 += p1[i];
    sum2 += p2[i];
  }
  const mean1 = sum1 / n;
  const mean2 = sum2 / n;

  let num = 0, den1 = 0, den2 = 0;
  for (let i = 0; i < n; i++) {
    const d1 = p1[i] - mean1;
    const d2 = p2[i] - mean2;
    num += d1 * d2;
    den1 += d1 * d1;
    den2 += d2 * d2;
  }

  const den = Math.sqrt(den1 * den2);
  return den > 1e-6 ? Math.max(-1, Math.min(1, num / den)) : 0;
}

/**
 * Assesses data quality for a ping given telemetry and intensity profile.
 */
export function evaluatePingQuality(
  pingIndex: number,
  intensity: number[] | Float32Array,
  rollDeg: number | null,
  pitchDeg: number | null,
  previousPingIntensity?: number[] | Float32Array,
  config: MotionConfig = DEFAULT_MOTION_CONFIG
): PingQualityResult {
  const reasons: string[] = [];
  let isMotion = false;
  let isDrop = false;
  let isSat = false;

  // 1. Attitude Telemetry Check
  if (rollDeg !== null && Math.abs(rollDeg) > config.maxRollDeg) {
    isMotion = true;
    reasons.push(`Roll exceeds limit (${Math.abs(rollDeg).toFixed(1)}° > ${config.maxRollDeg}°)`);
  }
  if (pitchDeg !== null && Math.abs(pitchDeg) > config.maxPitchDeg) {
    isMotion = true;
    reasons.push(`Pitch exceeds limit (${Math.abs(pitchDeg).toFixed(1)}° > ${config.maxPitchDeg}°)`);
  }

  // 2. Ping-to-ping Correlation Collapse
  if (previousPingIntensity) {
    const corr = pingCorrelation(intensity, previousPingIntensity);
    if (corr < config.minCorrelation) {
      isMotion = true;
      reasons.push(`Acoustic correlation collapse (r = ${corr.toFixed(2)} < ${config.minCorrelation})`);
    }
  }

  // 3. Dropout & Saturation Checks
  let sum = 0;
  let satCount = 0;
  for (let i = 0; i < intensity.length; i++) {
    const v = intensity[i];
    sum += v;
    if (v >= 250) satCount++;
  }
  const mean = intensity.length > 0 ? sum / intensity.length : 0;
  const satFrac = intensity.length > 0 ? satCount / intensity.length : 0;

  if (mean < config.dropoutThreshold) {
    isDrop = true;
    reasons.push(`Ping acoustic dropout (mean intensity ${mean.toFixed(1)} < ${config.dropoutThreshold})`);
  }
  if (satFrac > config.saturationThreshold) {
    isSat = true;
    reasons.push(`Receiver clipping/saturation (${(satFrac * 100).toFixed(0)}% samples saturated)`);
  }

  // Aggregate quality score [0, 1]
  let quality = 1.0;
  if (isMotion) quality -= 0.5;
  if (isDrop) quality -= 0.4;
  if (isSat) quality -= 0.2;
  quality = Math.max(0, Math.min(1, quality));

  return {
    pingIndex,
    qualityScore: quality,
    isMotionCorrupted: isMotion,
    isDropout: isDrop,
    isSaturated: isSat,
    reasons,
  };
}

/**
 * Checks overlap fraction between candidate bounding box and corrupted pings.
 * If overlap exceeds threshold (default 50%), the candidate is suppressed as motion/dropout artifact.
 */
export function computeCandidateMotionOverlap(
  pingStart: number,
  pingEnd: number,
  corruptedPingSet: Set<number>,
  suppressionOverlapThreshold = 0.50
): { overlapFraction: number; shouldSuppress: boolean } {
  const totalPings = Math.max(1, pingEnd - pingStart + 1);
  let corruptedCount = 0;

  for (let p = pingStart; p <= pingEnd; p++) {
    if (corruptedPingSet.has(p)) corruptedCount++;
  }

  const fraction = corruptedCount / totalPings;
  return {
    overlapFraction: fraction,
    shouldSuppress: fraction >= suppressionOverlapThreshold,
  };
}
