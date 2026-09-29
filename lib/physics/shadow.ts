/**
 * Acoustic Shadow Engine & Physical Relief Height Calculation
 * Section 22 & 23: Evaluates down-range acoustic shadows, shadow geometry consistency,
 * and physical vertical relief height h = (Ls * H) / (R + Ls).
 * 
 * NON-NEGOTIABLE RULE: Height is a PHYSICAL EVIDENCE FEATURE, NOT A CLASS IDENTIFIER.
 * NEVER assign classes based on height alone.
 */

export interface ShadowAnalysisResult {
  hasValidShadow: boolean;
  shadowLengthM: number;
  shadowLengthPx: number;
  shadowScore: number; // [0, 1]
  shadowSide: "correct" | "incorrect" | "absent";
  heightEstimateM: number | null;
  heightPlausibility: number; // [0, 1]
  explanation: string;
}

export function evaluateAcousticShadow(
  luminance: Float32Array,
  width: number,
  height: number,
  bbox: { x0: number; y0: number; x1: number; y1: number },
  nadirX: number,
  towfishAltitudeM: number = 8.5,
  rangeM: number = 75.0
): ShadowAnalysisResult {
  const centerTargetX = (bbox.x0 + bbox.x1) / 2;
  const isStarboard = centerTargetX >= nadirX;
  const metersPerPixel = rangeM / (width / 2);

  // Measure slant range in pixels and metres
  const slantRangePx = Math.abs(centerTargetX - nadirX);
  const slantRangeM = Math.max(4.0, slantRangePx * metersPerPixel);

  // Scan down-range (away from nadir)
  // Starboard: scan to the right (x increases)
  // Port: scan to the left (x decreases)
  const maxScanDistancePx = Math.min(180, Math.floor(width * 0.25));
  let darkPixelCount = 0;
  let shadowScanLength = 0;
  let inShadow = false;

  const sampleY0 = Math.max(0, bbox.y0);
  const sampleY1 = Math.min(height, bbox.y1);
  const sampleHeight = Math.max(1, sampleY1 - sampleY0);

  // Threshold for acoustic shadow: significantly below surrounding seabed noise floor
  const shadowIntensityThresh = 45;

  if (isStarboard) {
    const startX = bbox.x1;
    const endX = Math.min(width - 2, startX + maxScanDistancePx);
    for (let x = startX; x < endX; x++) {
      let colDarkCount = 0;
      for (let y = sampleY0; y < sampleY1; y++) {
        if (luminance[y * width + x] <= shadowIntensityThresh) {
          colDarkCount++;
        }
      }
      const darkFrac = colDarkCount / sampleHeight;
      if (darkFrac >= 0.35) {
        inShadow = true;
        darkPixelCount++;
        shadowScanLength = x - startX;
      } else if (inShadow && darkFrac < 0.20) {
        break; // End of shadow zone, seabed return resumes
      }
    }
  } else {
    const startX = bbox.x0;
    const endX = Math.max(2, startX - maxScanDistancePx);
    for (let x = startX; x > endX; x--) {
      let colDarkCount = 0;
      for (let y = sampleY0; y < sampleY1; y++) {
        if (luminance[y * width + x] <= shadowIntensityThresh) {
          colDarkCount++;
        }
      }
      const darkFrac = colDarkCount / sampleHeight;
      if (darkFrac >= 0.35) {
        inShadow = true;
        darkPixelCount++;
        shadowScanLength = startX - x;
      } else if (inShadow && darkFrac < 0.20) {
        break;
      }
    }
  }

  const shadowLengthM = Math.round(shadowScanLength * metersPerPixel * 10) / 10;
  const shadowScore = Math.min(1.0, shadowScanLength / 60);

  // Also check anti-causal direction (toward nadir) to ensure shadow is NOT pointing wrong way
  let antiCausalDark = 0;
  const antiScanPx = 30;
  if (isStarboard) {
    for (let x = Math.max(0, bbox.x0 - antiScanPx); x < bbox.x0; x++) {
      for (let y = sampleY0; y < sampleY1; y += 2) {
        if (luminance[y * width + x] <= shadowIntensityThresh) antiCausalDark++;
      }
    }
  } else {
    for (let x = bbox.x1; x < Math.min(width, bbox.x1 + antiScanPx); x++) {
      for (let y = sampleY0; y < sampleY1; y += 2) {
        if (luminance[y * width + x] <= shadowIntensityThresh) antiCausalDark++;
      }
    }
  }

  let shadowSide: "correct" | "incorrect" | "absent" = "absent";
  if (shadowScanLength >= 8 && shadowScanLength > antiCausalDark * 0.5) {
    shadowSide = "correct";
  } else if (antiCausalDark > shadowScanLength * 1.5 && antiCausalDark > 15) {
    shadowSide = "incorrect"; // Anti-causal depression / scouring
  } else {
    shadowSide = "absent";
  }

  // Calculate physical vertical relief: H = (Ls * Altitude) / (Ls + R)
  let heightEstimateM: number | null = null;
  let heightPlausibility = 0.5;

  if (shadowSide === "correct" && shadowLengthM >= 0.3) {
    const rawH = (shadowLengthM * towfishAltitudeM) / (shadowLengthM + slantRangeM);
    heightEstimateM = Math.round(rawH * 100) / 100;
    // Plausibility for marine debris: 0.2m to 6.0m is standard anthropogenic physical envelope
    heightPlausibility = heightEstimateM >= 0.2 && heightEstimateM <= 6.0 ? 0.92 : 0.40;
  } else if (shadowSide === "absent") {
    // Low relief / flat structure (e.g. flat net, buried plate)
    heightEstimateM = null;
    heightPlausibility = 0.50;
  } else {
    // Inconsistent shadow
    heightEstimateM = null;
    heightPlausibility = 0.10;
  }

  const hasValidShadow = shadowSide === "correct" && shadowScore >= 0.12;

  const explanation = hasValidShadow
    ? `Down-range acoustic shadow verified (${shadowLengthM}m, direction: ${isStarboard ? "starboard" : "port"} away from nadir). Physical relief height: ${heightEstimateM ?? "N/A"}m.`
    : shadowSide === "incorrect"
    ? `Anti-causal shadow points toward nadir (acoustic depression/scour, not a raised object).`
    : `Weak or absent down-range shadow (low physical relief or object lying flat on sediment).`;

  return {
    hasValidShadow,
    shadowLengthM,
    shadowLengthPx: shadowScanLength,
    shadowScore: Math.round(shadowScore * 100) / 100,
    shadowSide,
    heightEstimateM,
    heightPlausibility,
    explanation,
  };
}
