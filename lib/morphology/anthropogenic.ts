/**
 * Anthropogenic Anomaly & Large Structural / Wreck Morphology Head
 * Section 18 & 19: Open-set detection of artificial structures, mechanical objects, and shipwreck debris.
 * Quantifies specular acoustic reflectivity, geometric organization, and structural anomaly.
 * Enables honest routing to "unknown_manmade" (Unknown Anthropogenic Structure) when no known class fits.
 */

export interface AnthropogenicAnalysisResult {
  anthropogenicScore: number; // [0, 1] - Probability that the object is man-made
  anomalyScore: number; // [0, 1] - Degree of deviation from natural seabed background
  wreckScore: number; // [0, 1] - Large structural wreckage likelihood
  isAnthropogenic: boolean;
  explanation: string;
}

export function analyzeAnthropogenicAnomaly(
  luminance: Float32Array,
  width: number,
  height: number,
  bbox: { x0: number; y0: number; x1: number; y1: number },
  shadowScore: number = 0.5,
  heightEstimateM: number | null = null,
  circularScore: number = 0,
  trussScore: number = 0,
  linearScore: number = 0
): AnthropogenicAnalysisResult {
  const cropW = Math.max(10, bbox.x1 - bbox.x0);
  const cropH = Math.max(10, bbox.y1 - bbox.y0);

  // 1. Specular Acoustic Reflectivity (Metals, plastics, and dense man-made materials reflect intensely)
  let brightPixelCount = 0;
  let totalPixels = 0;
  let peakIntensity = 0;

  for (let cy = 0; cy < cropH; cy++) {
    const y = bbox.y0 + cy;
    if (y < 0 || y >= height) continue;
    for (let cx = 0; cx < cropW; cx++) {
      const x = bbox.x0 + cx;
      if (x < 0 || x >= width) continue;
      const lum = luminance[y * width + x];
      totalPixels++;
      if (lum > 140) brightPixelCount++;
      if (lum > peakIntensity) peakIntensity = lum;
    }
  }

  const specularRatio = totalPixels > 0 ? brightPixelCount / totalPixels : 0;

  // 2. Geometric Organization (Natural rocks and mud are amorphous; man-made objects have symmetry, lines, or rings)
  const geometricOrderScore = Math.max(circularScore, trussScore, linearScore);

  // 3. Shadow Coherence (A real solid object casts a clean, distinct down-range shadow)
  const shadowCoherence = Math.min(1.0, shadowScore * 1.25);

  // 4. Combined Anthropogenic Score
  // High specular reflectivity + high geometric organization + coherent shadow = Man-Made
  let anthropogenicScore = (
    specularRatio * 0.35 +
    geometricOrderScore * 0.40 +
    shadowCoherence * 0.25
  );

  // Boost if multiple structural heads agreed
  if (circularScore > 0.6 && trussScore > 0.6) {
    anthropogenicScore = Math.max(anthropogenicScore, 0.94); // Classical bicycle / vehicle truss signature
  }

  // 5. Large Structural / Wreck Score
  const areaM2 = (cropW * 0.15) * (cropH * 0.15); // rough metric footprint
  let wreckScore = 0;
  if (areaM2 >= 12.0 && shadowScore >= 0.15 && (heightEstimateM === null || heightEstimateM >= 1.5)) {
    wreckScore = Math.min(0.95, 0.50 + (areaM2 / 60) * 0.35 + (heightEstimateM ? heightEstimateM / 6 : 0.2));
  } else {
    wreckScore = Math.min(0.35, areaM2 / 20);
  }

  // 6. Anomaly Score: How strongly does this target stand out from baseline seabed noise?
  const anomalyScore = Math.min(0.98, Math.max(0.10, (peakIntensity / 255) * 0.6 + specularRatio * 0.4));

  const isAnthropogenic = anthropogenicScore >= 0.50 || (specularRatio >= 0.15 && shadowScore >= 0.10);

  const explanation = isAnthropogenic
    ? `Anthropogenic characteristics verified: organized geometry ${(geometricOrderScore * 100).toFixed(0)}%, specular acoustic reflectivity ${(specularRatio * 100).toFixed(0)}%, coherent shadow ${(shadowCoherence * 100).toFixed(0)}%.`
    : `Acoustic signature consistent with natural amorphous seafloor features (no rigid geometry).`;

  return {
    anthropogenicScore: Math.round(anthropogenicScore * 100) / 100,
    anomalyScore: Math.round(anomalyScore * 100) / 100,
    wreckScore: Math.round(wreckScore * 100) / 100,
    isAnthropogenic,
    explanation,
  };
}
