/**
 * SagarNetra - Sonar Physics: Shadow Relief Height Estimation
 * 
 * Fundamental Acoustic Shadow Formula:
 * h = (Ls * H) / (R + Ls)
 * 
 * where:
 *   h  = estimated physical target relief height (m)
 *   Ls = acoustic shadow length (m)
 *   H  = towfish altitude above seabed (m)
 *   R  = slant range to target highlight (m)
 * 
 * NON-NEGOTIABLE ARCHITECTURAL INVARIANT:
 * Height is a PHYSICAL EVIDENCE FEATURE, NOT an object class identifier.
 * NEVER assign classes directly from height brackets.
 */

export interface ShadowHeightResult {
  heightM: number;
  uncertaintyM: number;
  plausibilityScore: number; // [0, 1]
  explanation: string;
}

/**
 * Calculates physical relief height from acoustic shadow geometry.
 */
export function calculateShadowReliefHeight(
  shadowLengthM: number,
  towfishAltitudeM: number,
  slantRangeM: number,
  sensorBeamwidthDeg = 0.5
): ShadowHeightResult {
  if (shadowLengthM <= 0 || towfishAltitudeM <= 0 || slantRangeM <= 0) {
    return {
      heightM: 0,
      uncertaintyM: 0.1,
      plausibilityScore: 0.2, // flat object or buried
      explanation: 'No discernable acoustic shadow relief detected (object may be flat or buried).'
    };
  }

  // Exact shadow height formula: h = (Ls * H) / (R + Ls)
  const denom = slantRangeM + shadowLengthM;
  const heightM = (shadowLengthM * towfishAltitudeM) / denom;

  // Uncertainty model: propagates altitude error (±0.1m) and shadow edge resolution (±0.15m)
  const deltaLs = 0.15;
  const deltaH = 0.10;
  const dh_dLs = (towfishAltitudeM * slantRangeM) / (denom * denom);
  const dh_dH = shadowLengthM / denom;
  const uncertaintyM = Math.sqrt(
    Math.pow(dh_dLs * deltaLs, 2) + Math.pow(dh_dH * deltaH, 2)
  );

  // Plausibility check: underwater debris heights typically range between 0.1m and 15m
  let plausibility = 1.0;
  if (heightM < 0.1) plausibility = 0.4;
  else if (heightM > 12.0) plausibility = 0.3; // likely bathymetric ridge or pinnacle, not small debris

  return {
    heightM: Math.round(heightM * 100) / 100,
    uncertaintyM: Math.round(uncertaintyM * 100) / 100,
    plausibilityScore: Math.round(plausibility * 100) / 100,
    explanation: `Calculated shadow relief height: ${heightM.toFixed(2)}m (±${uncertaintyM.toFixed(2)}m) from shadow length ${shadowLengthM.toFixed(1)}m and altitude ${towfishAltitudeM.toFixed(1)}m.`,
  };
}
