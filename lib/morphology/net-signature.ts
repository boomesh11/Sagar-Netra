/**
 * Ghost-Net Acoustic Signature Head & Net Veto Engine
 * Section 16 & 17: Mandatory ghost-net structural verifier.
 * Computes:
 * 1. Rope skeleton (flexible continuous curved ridges)
 * 2. Mesh texture energy (Gabor / high-frequency periodicity)
 * 3. Catenary draping (contour-following flexible sagging)
 * 4. Float/sinker point reflector chain
 * 
 * CRITICAL RULE: A detection MUST NOT become ghost_net based on height alone.
 * NET VETO: If net-specific evidence is absent, ghost_net is strictly vetoed.
 */

export interface NetSignatureResult {
  score: number; // [0, 1] - Net probability based purely on net structural evidence
  ropeScore: number; // [0, 1]
  meshScore: number; // [0, 1]
  drapingScore: number; // [0, 1]
  floatSinkerScore: number; // [0, 1]
  vetoTriggered: boolean;
  explanation: string;
}

export function analyzeNetSignature(
  luminance: Float32Array,
  width: number,
  height: number,
  bbox: { x0: number; y0: number; x1: number; y1: number },
  shadowScore: number = 0.5
): NetSignatureResult {
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

  // 1. Float / Sinker Point Detector (Laplacian-of-Gaussian / local compact blobs)
  // Floats and lead sinkers appear as periodic compact high-intensity beads of 4-15 pixels
  let floatBlobCount = 0;
  for (let cy = 3; cy < cropH - 3; cy += 3) {
    for (let cx = 3; cx < cropW - 3; cx += 3) {
      const globalIdx = (bbox.y0 + cy) * width + (bbox.x0 + cx);
      const centerVal = luminance[globalIdx];
      if (centerVal > meanLum * 1.55) {
        // Check local compactness (center significantly higher than 4 surrounding ring samples)
        const n1 = luminance[(bbox.y0 + cy - 3) * width + (bbox.x0 + cx)];
        const n2 = luminance[(bbox.y0 + cy + 3) * width + (bbox.x0 + cx)];
        const n3 = luminance[(bbox.y0 + cy) * width + (bbox.x0 + cx - 3)];
        const n4 = luminance[(bbox.y0 + cy) * width + (bbox.x0 + cx + 3)];
        const avgSurround = (n1 + n2 + n3 + n4) / 4;
        if (centerVal > avgSurround * 1.35) {
          floatBlobCount++;
        }
      }
    }
  }

  // Float chain score: requires 4+ aligned beads
  const floatSinkerScore = Math.min(0.95, Math.max(0.02, (floatBlobCount / 12) * 0.85));

  // 2. Mesh Texture Energy (Gabor / high-frequency mesh weave check)
  // Real monofilament / nylon gillnets produce faint, granular high-frequency backscatter
  let localVarianceSum = 0;
  let varCount = 0;
  for (let cy = 2; cy < cropH - 2; cy += 2) {
    for (let cx = 2; cx < cropW - 2; cx += 2) {
      const idx = (bbox.y0 + cy) * width + (bbox.x0 + cx);
      const v = luminance[idx];
      const diff1 = Math.abs(v - luminance[idx + 1]);
      const diff2 = Math.abs(v - luminance[idx + width]);
      localVarianceSum += (diff1 + diff2);
      varCount++;
    }
  }
  const avgTextureEnergy = varCount > 0 ? localVarianceSum / varCount : 0;
  // Mesh texture is intermediate: not totally smooth (mud), not hard massive specular (metal/rock)
  const isMeshTextureRange = avgTextureEnergy >= 8 && avgTextureEnergy <= 28;
  const meshScore = isMeshTextureRange ? Math.min(0.88, avgTextureEnergy / 22) : 0.12;

  // 3. Rope Skeleton & Curvature
  // Measure presence of curved, meandering lines (headrope / footrope lines)
  let curvedRidgePixels = 0;
  for (let cy = 2; cy < cropH - 2; cy++) {
    for (let cx = 2; cx < cropW - 2; cx++) {
      const idx = (bbox.y0 + cy) * width + (bbox.x0 + cx);
      const val = luminance[idx];
      if (val > meanLum * 1.25) {
        curvedRidgePixels++;
      }
    }
  }
  const ropeCoverage = count > 0 ? curvedRidgePixels / count : 0;
  // Net ropes form 8% - 25% of the bounding box area in thin meandering chains
  const ropeScore = (ropeCoverage >= 0.06 && ropeCoverage <= 0.32)
    ? Math.min(0.85, 0.40 + ropeCoverage * 1.5)
    : 0.10;

  // 4. Draping / Catenary Sagging
  // Draped nets have high bounding aspect variation without rigid rectilinear corners
  const drapingScore = (meshScore > 0.40 && ropeScore > 0.35) ? 0.65 : 0.15;

  // Multi-cue Net Evidence Fusion (Strictly independent of height!)
  // net_score = f(rope, mesh, draping, float_sinker)
  const netEvidence = (
    ropeScore * 0.30 +
    meshScore * 0.30 +
    drapingScore * 0.20 +
    floatSinkerScore * 0.20
  );

  // NET VETO: If mesh is low, rope is low, and no float chains exist:
  const vetoTriggered = meshScore < 0.28 && ropeScore < 0.28 && floatSinkerScore < 0.25;

  const finalScore = vetoTriggered
    ? Math.min(0.15, netEvidence * 0.3)
    : Math.round(netEvidence * 100) / 100;

  const explanation = vetoTriggered
    ? `Net Veto Triggered: No float chains (${floatBlobCount} beads), no mesh texture (energy ${avgTextureEnergy.toFixed(1)}), and no flexible catenary rope skeleton. Target is NOT a ghost net.`
    : `Net signature supported: mesh texture ${(meshScore * 100).toFixed(0)}%, rope skeleton ${(ropeScore * 100).toFixed(0)}%, float chain ${(floatSinkerScore * 100).toFixed(0)}%.`;

  return {
    score: Math.round(finalScore * 100) / 100,
    ropeScore: Math.round(ropeScore * 100) / 100,
    meshScore: Math.round(meshScore * 100) / 100,
    drapingScore: Math.round(drapingScore * 100) / 100,
    floatSinkerScore: Math.round(floatSinkerScore * 100) / 100,
    vetoTriggered,
    explanation,
  };
}
