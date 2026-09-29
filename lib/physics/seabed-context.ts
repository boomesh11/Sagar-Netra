/**
 * Seabed Context & Sand-Ripple Suppression Engine
 * Section 20 & 21: Prevents false positive clusters on natural sand ripples, rock fields, and mud textures.
 * Performs annular contrast analysis: compares internal candidate texture against surrounding annular seabed.
 * If periodic sand ripple texture continues seamlessly into the surrounding area, the candidate is
 * classified as natural seabed and suppressed.
 */

export interface SeabedContextResult {
  naturalSeabedScore: number; // [0, 1] - High means natural sand ripple / sediment
  isNaturalSeabed: boolean;
  annularContrast: number; // [0, 1] - High means candidate is isolated and distinct from surroundings
  isSuppressedRipple: boolean;
  explanation: string;
}

export function evaluateSeabedContext(
  luminance: Float32Array,
  width: number,
  height: number,
  bbox: { x0: number; y0: number; x1: number; y1: number }
): SeabedContextResult {
  const boxW = Math.max(10, bbox.x1 - bbox.x0);
  const boxH = Math.max(10, bbox.y1 - bbox.y0);

  // 1. Inside candidate statistics
  let insideLumSum = 0;
  let insideVariationSum = 0;
  let insideCount = 0;

  for (let y = bbox.y0; y < bbox.y1; y += 2) {
    if (y < 0 || y >= height) continue;
    for (let x = bbox.x0; x < bbox.x1; x += 2) {
      if (x < 0 || x >= width) continue;
      const v = luminance[y * width + x];
      insideLumSum += v;
      if (x + 2 < bbox.x1) {
        insideVariationSum += Math.abs(v - luminance[y * width + (x + 2)]);
      }
      insideCount++;
    }
  }

  const insideMean = insideCount > 0 ? insideLumSum / insideCount : 50;
  const insideTexturePeriodicity = insideCount > 0 ? insideVariationSum / insideCount : 0;

  // 2. Surrounding Annular Ring (expand bbox by 1.5x to 2.5x to sample regional background)
  const ringPadX = Math.round(boxW * 0.8);
  const ringPadY = Math.round(boxH * 0.8);
  const ringX0 = Math.max(0, bbox.x0 - ringPadX);
  const ringX1 = Math.min(width, bbox.x1 + ringPadX);
  const ringY0 = Math.max(0, bbox.y0 - ringPadY);
  const ringY1 = Math.min(height, bbox.y1 + ringPadY);

  let ringLumSum = 0;
  let ringVariationSum = 0;
  let ringCount = 0;

  for (let y = ringY0; y < ringY1; y += 3) {
    for (let x = ringX0; x < ringX1; x += 3) {
      // Exclude the interior bounding box
      const isInside = x >= bbox.x0 && x <= bbox.x1 && y >= bbox.y0 && y <= bbox.y1;
      if (!isInside) {
        const v = luminance[y * width + x];
        ringLumSum += v;
        if (x + 3 < ringX1) {
          ringVariationSum += Math.abs(v - luminance[y * width + (x + 3)]);
        }
        ringCount++;
      }
    }
  }

  const ringMean = ringCount > 0 ? ringLumSum / ringCount : insideMean;
  const ringTexturePeriodicity = ringCount > 0 ? ringVariationSum / ringCount : insideTexturePeriodicity;

  // Pattern contrast: How distinct is the candidate from the regional background?
  const intensityContrast = Math.abs(insideMean - ringMean) / Math.max(20, ringMean);
  const textureContrast = Math.abs(insideTexturePeriodicity - ringTexturePeriodicity) / Math.max(5, ringTexturePeriodicity);

  // Annular contrast score [0, 1]
  const annularContrast = Math.min(1.0, intensityContrast * 0.6 + textureContrast * 0.4);

  // Ripple continuity: If surrounding ring has nearly identical high periodicity to the candidate,
  // it is part of a broad regional sand ripple field!
  const hasContinuousRegionalPeriodicity = (
    ringTexturePeriodicity >= 6.0 &&
    insideTexturePeriodicity >= 6.0 &&
    Math.abs(insideTexturePeriodicity - ringTexturePeriodicity) < 4.0
  );

  let naturalSeabedScore = 0;
  let isSuppressedRipple = false;

  if (hasContinuousRegionalPeriodicity && annularContrast < 0.25) {
    // Definite sand ripple field: texture continues seamlessly through surrounding seabed
    naturalSeabedScore = 0.88;
    isSuppressedRipple = true;
  } else if (annularContrast < 0.18) {
    naturalSeabedScore = 0.72;
    isSuppressedRipple = true;
  } else {
    // Isolated, distinct object standing out against background
    naturalSeabedScore = Math.max(0.04, 0.40 - annularContrast * 0.4);
    isSuppressedRipple = false;
  }

  const isNaturalSeabed = naturalSeabedScore >= 0.65;

  const explanation = isSuppressedRipple
    ? `Suppressed: Periodic sand ripple texture continues seamlessly into surrounding seabed (annular contrast: ${(annularContrast * 100).toFixed(0)}%). No isolated raised structure.`
    : `Candidate is structurally localized and distinct from surrounding seafloor (annular contrast: ${(annularContrast * 100).toFixed(0)}%).`;

  return {
    naturalSeabedScore: Math.round(naturalSeabedScore * 100) / 100,
    isNaturalSeabed,
    annularContrast: Math.round(annularContrast * 100) / 100,
    isSuppressedRipple,
    explanation,
  };
}
