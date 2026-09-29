/**
 * SagarNetra - Sonar Geometry & Slant-to-Ground Range Conversion
 * 
 * Fundamental Acoustic Geometry:
 * G = sqrt(R² - H²)
 * where:
 *   R = slant range (m)
 *   H = towfish altitude above seabed (m)
 *   G = ground/horizontal range (m)
 */

export interface SlantRangeConfig {
  towfishAltitudeM: number;
  slantRangeResolutionM: number;
  soundVelocityMPerS: number;
}

/**
 * Converts a slant range measurement to horizontal ground range.
 * If slant range R is less than towfish altitude H, the acoustic pulse has not yet
 * reached the seabed (water column). Returns 0 ground range.
 */
export function slantToGroundRange(
  slantRangeM: number,
  altitudeM: number
): { groundRangeM: number; inWaterColumn: boolean } {
  if (altitudeM <= 0 || slantRangeM < altitudeM) {
    return { groundRangeM: 0, inWaterColumn: true };
  }
  const groundRangeM = Math.sqrt(Math.max(0, slantRangeM * slantRangeM - altitudeM * altitudeM));
  return { groundRangeM, inWaterColumn: false };
}

/**
 * Resamples a 1D intensity ping from slant-range intervals to equidistant ground-range bins.
 */
export function correctPingSlantRange(
  slantPing: Float32Array | number[],
  altitudeM: number,
  maxSlantRangeM: number,
  numOutputGroundBins: number
): Float32Array {
  const numSlantSamples = slantPing.length;
  const output = new Float32Array(numOutputGroundBins);
  
  const maxGroundRangeM = Math.sqrt(Math.max(0, maxSlantRangeM * maxSlantRangeM - altitudeM * altitudeM));
  if (maxGroundRangeM <= 0) return output;

  const groundBinSizeM = maxGroundRangeM / numOutputGroundBins;

  for (let gIdx = 0; gIdx < numOutputGroundBins; gIdx++) {
    const gRangeM = (gIdx + 0.5) * groundBinSizeM;
    const requiredSlantM = Math.sqrt(gRangeM * gRangeM + altitudeM * altitudeM);
    const slantSampleIdx = (requiredSlantM / maxSlantRangeM) * numSlantSamples;

    if (slantSampleIdx >= 0 && slantSampleIdx < numSlantSamples - 1) {
      const low = Math.floor(slantSampleIdx);
      const frac = slantSampleIdx - low;
      output[gIdx] = slantPing[low] * (1 - frac) + slantPing[low + 1] * frac;
    } else if (slantSampleIdx < numSlantSamples) {
      output[gIdx] = slantPing[Math.floor(slantSampleIdx)];
    }
  }

  return output;
}
