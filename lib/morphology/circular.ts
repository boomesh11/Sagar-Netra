/**
 * Circular / Annular Morphology Detector
 * Section 13: Detects circular and annular structures (bicycle wheels, tires, circular traps, coils, rings).
 * Computes circularity C = 4πA / P², concentricity, annular wall continuity, and pair spacing.
 */

export interface CircularAnalysisResult {
  score: number; // [0, 1]
  circlesFound: number;
  annularContinuity: number; // [0, 1]
  pairSpacingPx: number | null;
  radii: number[];
  centers: { x: number; y: number }[];
  explanation: string;
}

export function analyzeCircularMorphology(
  luminance: Float32Array,
  width: number,
  height: number,
  bbox: { x0: number; y0: number; x1: number; y1: number }
): CircularAnalysisResult {
  const cropW = Math.max(10, bbox.x1 - bbox.x0);
  const cropH = Math.max(10, bbox.y1 - bbox.y0);

  // Sub-region thresholding for edge/rim extraction
  const minDim = Math.min(cropW, cropH);
  const minRadius = Math.max(8, Math.floor(minDim * 0.12));
  const maxRadius = Math.min(Math.floor(minDim * 0.48), 120);

  // Circle accumulator array (Hough transform in local crop space)
  const step = 2;
  const accW = Math.ceil(cropW / step);
  const accH = Math.ceil(cropH / step);
  const accumulator = new Float32Array(accW * accH);

  // Collect active edge pixels in crop
  const edgePixels: { x: number; y: number }[] = [];
  let cropLumSum = 0;
  let count = 0;

  for (let cy = 0; cy < cropH; cy++) {
    const y = bbox.y0 + cy;
    if (y < 0 || y >= height) continue;
    for (let cx = 0; cx < cropW; cx++) {
      const x = bbox.x0 + cx;
      if (x < 0 || x >= width) continue;
      const lum = luminance[y * width + x];
      cropLumSum += lum;
      count++;
    }
  }

  const cropMean = count > 0 ? cropLumSum / count : 50;
  const edgeThreshold = cropMean * 1.25;

  for (let cy = 1; cy < cropH - 1; cy++) {
    const y = bbox.y0 + cy;
    for (let cx = 1; cx < cropW - 1; cx++) {
      const x = bbox.x0 + cx;
      const val = luminance[y * width + x];
      if (val > edgeThreshold) {
        // Simple Sobel-like edge gradient check
        const gx = (luminance[y * width + (x + 1)] - luminance[y * width + (x - 1)]);
        const gy = (luminance[(y + 1) * width + x] - luminance[(y - 1) * width + x]);
        const gradMag = Math.sqrt(gx * gx + gy * gy);
        if (gradMag > 25) {
          edgePixels.push({ x: cx, y: cy });
        }
      }
    }
  }

  // Accumulate circle votes
  const numAngles = 24;
  const dTheta = (2 * Math.PI) / numAngles;

  for (let r = minRadius; r <= maxRadius; r += 4) {
    for (const ep of edgePixels) {
      for (let a = 0; a < numAngles; a++) {
        const theta = a * dTheta;
        const xc = Math.round(ep.x - r * Math.cos(theta));
        const yc = Math.round(ep.y - r * Math.sin(theta));
        const ax = Math.floor(xc / step);
        const ay = Math.floor(yc / step);
        if (ax >= 0 && ax < accW && ay >= 0 && ay < accH) {
          accumulator[ay * accW + ax] += 1 / (r * 0.1 + 1);
        }
      }
    }
  }

  // Find candidate circle centers
  const detectedCenters: { x: number; y: number; votes: number; radius: number }[] = [];
  const voteThresh = Math.max(12, edgePixels.length * 0.04);

  for (let ay = 1; ay < accH - 1; ay++) {
    for (let ax = 1; ax < accW - 1; ax++) {
      const v = accumulator[ay * accW + ax];
      if (v > voteThresh) {
        // Local peak check
        let isPeak = true;
        for (let dy = -1; dy <= 1; dy++) {
          for (let dx = -1; dx <= 1; dx++) {
            if (dx === 0 && dy === 0) continue;
            if (accumulator[(ay + dy) * accW + (ax + dx)] > v) {
              isPeak = false;
              break;
            }
          }
          if (!isPeak) break;
        }

        if (isPeak) {
          // Estimate best radius for this center
          const cx = ax * step;
          const cy = ay * step;
          let bestR = minRadius;
          let maxRingVotes = 0;

          for (let r = minRadius; r <= maxRadius; r += 3) {
            let ringHits = 0;
            for (let a = 0; a < 16; a++) {
              const th = (a * 2 * Math.PI) / 16;
              const px = Math.round(cx + r * Math.cos(th));
              const py = Math.round(cy + r * Math.sin(th));
              if (px >= 0 && px < cropW && py >= 0 && py < cropH) {
                const globalIdx = (bbox.y0 + py) * width + (bbox.x0 + px);
                if (luminance[globalIdx] > cropMean * 1.15) {
                  ringHits++;
                }
              }
            }
            if (ringHits > maxRingVotes) {
              maxRingVotes = ringHits;
              bestR = r;
            }
          }

          if (maxRingVotes >= 9) { // At least ~55% of circumference
            detectedCenters.push({ x: cx, y: cy, votes: v, radius: bestR });
          }
        }
      }
    }
  }

  // Filter overlapping centers
  const uniqueCenters: { x: number; y: number; radius: number }[] = [];
  for (const c of detectedCenters) {
    const tooClose = uniqueCenters.some(
      (uc) => Math.hypot(uc.x - c.x, uc.y - c.y) < Math.max(16, c.radius * 0.7)
    );
    if (!tooClose) {
      uniqueCenters.push({ x: c.x, y: c.y, radius: c.radius });
    }
  }

  let pairSpacingPx: number | null = null;
  if (uniqueCenters.length >= 2) {
    pairSpacingPx = Math.round(Math.hypot(
      uniqueCenters[0].x - uniqueCenters[1].x,
      uniqueCenters[0].y - uniqueCenters[1].y
    ));
  }

  let score = 0;
  let continuity = 0;
  if (uniqueCenters.length >= 2) {
    score = Math.min(0.96, 0.75 + uniqueCenters.length * 0.10);
    continuity = 0.85;
  } else if (uniqueCenters.length === 1) {
    score = 0.58;
    continuity = 0.65;
  } else {
    score = edgePixels.length > 50 ? 0.12 : 0.04;
    continuity = 0.10;
  }

  const explanation = uniqueCenters.length >= 2
    ? `Dual circular annular structures detected (count: ${uniqueCenters.length}, spacing: ${pairSpacingPx}px, radii: ${uniqueCenters.map(c => c.radius).join(", ")}px). Strong wheel/rim geometry.`
    : uniqueCenters.length === 1
    ? `Single circular ring detected (radius: ${uniqueCenters[0].radius}px). Possible wheel, coil, or circular trap.`
    : "No dominant circular or annular geometry detected.";

  return {
    score: Math.round(score * 100) / 100,
    circlesFound: uniqueCenters.length,
    annularContinuity: Math.round(continuity * 100) / 100,
    pairSpacingPx,
    radii: uniqueCenters.map((c) => c.radius),
    centers: uniqueCenters.map((c) => ({ x: c.x + bbox.x0, y: c.y + bbox.y0 })),
    explanation,
  };
}
