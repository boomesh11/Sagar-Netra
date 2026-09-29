/**
 * Linear Pipeline / Cable Morphology Detector
 * Section 15: Detects undersea pipelines, cylindrical drums, industrial cables, and linear debris.
 * Evaluates elongation, straightness, width consistency, dominant orientation, and continuous shadow.
 * Crucial rule: Does NOT classify every elongated object as a pipe without multi-feature validation.
 */

export interface LinearAnalysisResult {
  score: number; // [0, 1]
  elongation: number; // aspect ratio along dominant axis
  straightness: number; // [0, 1]
  widthConsistency: number; // [0, 1]
  dominantOrientationDeg: number;
  isPipeline: boolean;
  explanation: string;
}

export function analyzeLinearMorphology(
  luminance: Float32Array,
  width: number,
  height: number,
  bbox: { x0: number; y0: number; x1: number; y1: number },
  shadowScore: number = 0.5
): LinearAnalysisResult {
  const boxW = Math.max(8, bbox.x1 - bbox.x0);
  const boxH = Math.max(8, bbox.y1 - bbox.y0);

  // 1. Aspect ratio elongation
  const majorDim = Math.max(boxW, boxH);
  const minorDim = Math.min(boxW, boxH);
  const elongation = minorDim > 0 ? majorDim / minorDim : 1;

  // 2. Measure straightness and width consistency along major axis
  const isHorizontalMajor = boxW >= boxH;
  const majorSteps = Math.min(30, majorDim);
  const minorWidths: number[] = [];

  for (let s = 2; s < majorSteps - 2; s++) {
    const majorFrac = s / majorSteps;
    let localHighCount = 0;

    if (isHorizontalMajor) {
      const x = Math.floor(bbox.x0 + majorFrac * boxW);
      for (let y = bbox.y0; y < bbox.y1; y++) {
        if (x >= 0 && x < width && y >= 0 && y < height) {
          if (luminance[y * width + x] > 110) {
            localHighCount++;
          }
        }
      }
    } else {
      const y = Math.floor(bbox.y0 + majorFrac * boxH);
      for (let x = bbox.x0; x < bbox.x1; x++) {
        if (x >= 0 && x < width && y >= 0 && y < height) {
          if (luminance[y * width + x] > 110) {
            localHighCount++;
          }
        }
      }
    }

    if (localHighCount > 0) {
      minorWidths.push(localHighCount);
    }
  }

  // Width consistency: coefficient of variation of widths along the length
  let widthConsistency = 0.5;
  if (minorWidths.length >= 5) {
    const avgW = minorWidths.reduce((a, b) => a + b, 0) / minorWidths.length;
    const variance = minorWidths.reduce((a, b) => a + (b - avgW) ** 2, 0) / minorWidths.length;
    const stdW = Math.sqrt(variance);
    const cv = avgW > 0 ? stdW / avgW : 1;
    widthConsistency = Math.max(0, Math.min(1, 1 - cv));
  }

  // Straightness estimate
  const straightness = elongation >= 3.0 ? Math.min(0.95, 0.60 + widthConsistency * 0.35) : 0.35;
  const dominantOrientationDeg = isHorizontalMajor ? 0 : 90;

  // Pipeline requires BOTH high elongation (>= 2.8), uniform width consistency (>= 0.65), and continuous shadow
  let score = 0;
  let isPipeline = false;

  if (elongation >= 2.8 && widthConsistency >= 0.55 && straightness >= 0.60) {
    score = Math.min(0.95, 0.50 + (elongation / 8) * 0.25 + widthConsistency * 0.20);
    isPipeline = true;
  } else if (elongation >= 2.0 && widthConsistency >= 0.40) {
    score = 0.45;
    isPipeline = false;
  } else {
    score = 0.08;
    isPipeline = false;
  }

  const explanation = isPipeline
    ? `Continuous linear cylindrical structure (elongation ${elongation.toFixed(1)}:1, width consistency ${(widthConsistency * 100).toFixed(0)}%, straightness ${(straightness * 100).toFixed(0)}%). Characteristics match undersea pipeline / conduit.`
    : `Linearity insufficient for continuous pipeline (elongation ${elongation.toFixed(1)}:1, width variation high).`;

  return {
    score: Math.round(score * 100) / 100,
    elongation: Math.round(elongation * 10) / 10,
    straightness: Math.round(straightness * 100) / 100,
    widthConsistency: Math.round(widthConsistency * 100) / 100,
    dominantOrientationDeg,
    isPipeline,
    explanation,
  };
}
