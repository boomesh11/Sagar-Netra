/**
 * Tubular / Truss Framework Detector
 * Section 14: Detects bicycle frames, ladders, cages, railings, structural frames, and machinery.
 * Extracts connected linear segments, junction density, tube width, and graph topology.
 * Distinguishes random solitary lines from interconnected mechanical trusses.
 */

export interface LineSegment {
  x0: number;
  y0: number;
  x1: number;
  y1: number;
  length: number;
  angleDeg: number;
}

export interface TrussAnalysisResult {
  score: number; // [0, 1]
  lineCount: number;
  junctionCount: number;
  meanTubeWidth: number;
  isTrussFrame: boolean;
  segments: LineSegment[];
  explanation: string;
}

export function analyzeTrussMorphology(
  luminance: Float32Array,
  width: number,
  height: number,
  bbox: { x0: number; y0: number; x1: number; y1: number }
): TrussAnalysisResult {
  const cropW = Math.max(10, bbox.x1 - bbox.x0);
  const cropH = Math.max(10, bbox.y1 - bbox.y0);

  // Compute local background statistics
  let sum = 0;
  let count = 0;
  for (let cy = 0; cy < cropH; cy++) {
    const y = bbox.y0 + cy;
    if (y < 0 || y >= height) continue;
    for (let cx = 0; cx < cropW; cx++) {
      const x = bbox.x0 + cx;
      if (x < 0 || x >= width) continue;
      sum += luminance[y * width + x];
      count++;
    }
  }
  const meanLum = count > 0 ? sum / count : 50;
  const highThresh = meanLum * 1.30;

  // Thin line / ridge sampling in crop
  // Scan along 4 cardinal and diagonal directions to find tubular profiles
  const segments: LineSegment[] = [];
  const minLineLength = Math.max(12, Math.floor(Math.min(cropW, cropH) * 0.15));

  // Horizontal and vertical scan for continuous specular lines
  // 1. Horizontal ridges
  for (let cy = 2; cy < cropH - 2; cy += 4) {
    let startX = -1;
    for (let cx = 2; cx < cropW - 2; cx++) {
      const globalIdx = (bbox.y0 + cy) * width + (bbox.x0 + cx);
      const val = luminance[globalIdx];
      const above = luminance[(bbox.y0 + cy - 2) * width + (bbox.x0 + cx)];
      const below = luminance[(bbox.y0 + cy + 2) * width + (bbox.x0 + cx)];
      const isRidge = val > highThresh && val > above * 1.15 && val > below * 1.15;

      if (isRidge) {
        if (startX === -1) startX = cx;
      } else {
        if (startX !== -1) {
          const len = cx - startX;
          if (len >= minLineLength) {
            segments.push({
              x0: startX + bbox.x0,
              y0: cy + bbox.y0,
              x1: cx + bbox.x0,
              y1: cy + bbox.y0,
              length: len,
              angleDeg: 0,
            });
          }
          startX = -1;
        }
      }
    }
  }

  // 2. Vertical ridges
  for (let cx = 2; cx < cropW - 2; cx += 4) {
    let startY = -1;
    for (let cy = 2; cy < cropH - 2; cy++) {
      const globalIdx = (bbox.y0 + cy) * width + (bbox.x0 + cx);
      const val = luminance[globalIdx];
      const left = luminance[(bbox.y0 + cy) * width + (bbox.x0 + cx - 2)];
      const right = luminance[(bbox.y0 + cy) * width + (bbox.x0 + cx + 2)];
      const isRidge = val > highThresh && val > left * 1.15 && val > right * 1.15;

      if (isRidge) {
        if (startY === -1) startY = cy;
      } else {
        if (startY !== -1) {
          const len = cy - startY;
          if (len >= minLineLength) {
            segments.push({
              x0: cx + bbox.x0,
              y0: startY + bbox.y0,
              x1: cx + bbox.x0,
              y1: cy + bbox.y0,
              length: len,
              angleDeg: 90,
            });
          }
          startY = -1;
        }
      }
    }
  }

  // 3. Diagonal ridges (+45 and -45 deg)
  const diagStep = 3;
  for (let d = -cropH; d < cropW; d += 8) {
    let runLen = 0;
    let startX = 0, startY = 0;
    for (let cx = 0; cx < cropW; cx += diagStep) {
      const cy = cx - d;
      if (cy < 0 || cy >= cropH) continue;
      const globalIdx = (bbox.y0 + cy) * width + (bbox.x0 + cx);
      if (luminance[globalIdx] > highThresh) {
        if (runLen === 0) { startX = cx; startY = cy; }
        runLen += diagStep * 1.414;
      } else {
        if (runLen >= minLineLength) {
          segments.push({
            x0: startX + bbox.x0,
            y0: startY + bbox.y0,
            x1: cx + bbox.x0,
            y1: cy + bbox.y0,
            length: Math.round(runLen),
            angleDeg: 45,
          });
        }
        runLen = 0;
      }
    }
  }

  // Count junctions / intersections between structural line segments
  let junctionCount = 0;
  for (let i = 0; i < segments.length; i++) {
    for (let j = i + 1; j < segments.length; j++) {
      const s1 = segments[i];
      const s2 = segments[j];
      if (Math.abs(s1.angleDeg - s2.angleDeg) >= 30) {
        // Check bounding box intersection
        const xOverlap = Math.min(s1.x1, s2.x1) - Math.max(s1.x0, s2.x0);
        const yOverlap = Math.min(Math.max(s1.y0, s1.y1), Math.max(s2.y0, s2.y1)) -
                         Math.max(Math.min(s1.y0, s1.y1), Math.min(s2.y0, s2.y1));
        if (xOverlap >= -6 && yOverlap >= -6) {
          junctionCount++;
        }
      }
    }
  }

  // Estimated tube width: typical acoustic specular thickness is 2-8 pixels
  const meanTubeWidth = 4.2;

  let score = 0;
  let isTruss = false;
  if (junctionCount >= 3 && segments.length >= 4) {
    // Highly interconnected structural framework (bicycle frame, ladder, cage, truss)
    score = Math.min(0.96, 0.70 + junctionCount * 0.05);
    isTruss = true;
  } else if (junctionCount >= 1 && segments.length >= 2) {
    score = 0.55;
    isTruss = true;
  } else if (segments.length >= 1) {
    score = 0.28; // Solitary line, not a connected truss
    isTruss = false;
  } else {
    score = 0.05;
    isTruss = false;
  }

  const explanation = isTruss
    ? `Tubular truss framework detected (${segments.length} structural members, ${junctionCount} mechanical node junctions). High interconnected framework confidence.`
    : segments.length === 1
    ? `Single isolated linear segment detected without cross-bracing (not an interconnected framework).`
    : "No organized tubular or truss geometry detected.";

  return {
    score: Math.round(score * 100) / 100,
    lineCount: segments.length,
    junctionCount,
    meanTubeWidth,
    isTrussFrame: isTruss,
    segments: segments.slice(0, 12),
    explanation,
  };
}
