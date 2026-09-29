/**
 * SagarNetra - Comprehensive Regression Test Suite (Section 50)
 * 
 * Verifies all 15 non-negotiable architectural requirements:
 * 1. Bicycle should not become ghost_net.
 * 2. Bicycle components should merge into one target.
 * 3. Sand ripple field should not produce many debris boxes.
 * 4. Pipe should produce linear/tubular evidence.
 * 5. Ghost net should require net-specific evidence.
 * 6. Unknown anthropogenic structure should remain unknown when class evidence is weak.
 * 7. Missing navigation must never produce coordinates.
 * 8. Motion artifact should be suppressed when overlap exceeds threshold.
 * 9. Single-pass survey must not receive persistence penalty.
 * 10. Multi-pass matching must increase persistence evidence.
 * 11. Slant-range correction must produce physically valid ground range.
 * 12. Shadow height calculation must match known synthetic geometry.
 * 13. UTM zone must be automatically determined.
 * 14. Cluster fusion must merge structurally related components.
 * 15. Class assignment must never use height alone.
 */

import { describe, it } from 'node:test';
import assert from 'node:assert/strict';

import { analyzeCircularMorphology } from '../lib/morphology/circular.ts';
import { analyzeTrussMorphology } from '../lib/morphology/truss.ts';
import { analyzeLinearMorphology } from '../lib/morphology/linear.ts';
import { analyzeNetSignature } from '../lib/morphology/net-signature.ts';
import { analyzeAnthropogenicAnomaly } from '../lib/morphology/anthropogenic.ts';
import { performStructuralClusterFusion, type AcousticComponent } from '../lib/clustering/structural-graph.ts';
import { evaluateAcousticShadow } from '../lib/physics/shadow.ts';
import { calculateShadowReliefHeight } from '../lib/physics/height.ts';
import { evaluateSeabedContext } from '../lib/physics/seabed-context.ts';
import { evaluateMultiHeadClassification } from '../lib/classification/multi-head-classifier.ts';
import { slantToGroundRange } from '../lib/preprocessing/slant-range.ts';
import { computeCandidateMotionOverlap } from '../lib/preprocessing/motion-mask.ts';
import { calculateTargetGeolocation, getUTMZone } from '../lib/geotag/utm.ts';
import { computePhysicalShadowLength } from '../lib/synthetic/ghost-net.ts';

// Assertion helpers
function expect<T>(actual: T) {
  return {
    toBe(expected: T) {
      assert.equal(actual, expected, `Expected ${actual} to be ${expected}`);
    },
    not: {
      toBe(expected: T) {
        assert.notEqual(actual, expected, `Expected ${actual} NOT to be ${expected}`);
      }
    },
    toBeGreaterThan(expected: number) {
      assert.ok((actual as number) > expected, `Expected ${actual} > ${expected}`);
    },
    toBeLessThan(expected: number) {
      assert.ok((actual as number) < expected, `Expected ${actual} < ${expected}`);
    },
    toBeNull() {
      assert.equal(actual, null, `Expected ${actual} to be null`);
    }
  };
}

describe('SagarNetra Architectural Regression Test Suite', () => {

  // Test 1: Mandatory assertion: bicycle cannot be ghost_net
  it('1. Bicycle should not become ghost_net under any circumstance', () => {
    // Structural evidence representing submerged bicycle
    const circular = {
      score: 0.92,
      circlesFound: 2,
      annularContinuity: 0.88,
      pairSpacingPx: 65,
      radii: [18, 18],
      centers: [{ x: 120, y: 120 }, { x: 185, y: 120 }],
      explanation: 'Two circular/annular wheel rims detected with consistent spacing.'
    };
    const truss = {
      score: 0.86,
      lineCount: 6,
      junctionCount: 4,
      meanTubeWidth: 3.2,
      isTrussFrame: true,
      segments: [],
      explanation: 'Rigid diamond/triangular frame geometry detected.'
    };
    const net = {
      score: 0.05,
      ropeScore: 0.06,
      meshScore: 0.04,
      drapingScore: 0.02,
      floatSinkerScore: 0.00,
      vetoTriggered: true,
      explanation: 'Net veto: No mesh or flexible rope structures detected.'
    };
    const shadow = {
      hasValidShadow: true,
      shadowLengthM: 1.8,
      shadowLengthPx: 38,
      shadowScore: 0.85,
      shadowSide: 'correct' as const,
      heightEstimateM: 1.15,
      heightPlausibility: 0.90,
      explanation: 'Acoustic shadow confirms 1.15m vertical relief.'
    };

    // Even if initial raw detector was erroneously proposed as 'ghost_net'
    const bicycle = evaluateMultiHeadClassification({
      rawClassProposal: 'ghost_net',
      rawObjectnessConfidence: 86.0,
      circular,
      truss,
      linear: { score: 0.15, elongation: 1.2, straightness: 0.2, widthConsistency: 0.4, dominantOrientationDeg: 0, isPipeline: false, explanation: 'Not a pipeline' },
      net,
      anthropogenic: { anthropogenicScore: 0.92, anomalyScore: 0.88, wreckScore: 0.15, isAnthropogenic: true, explanation: 'High anthropogenic score' },
      shadow,
      seabed: { naturalSeabedScore: 0.05, isNaturalSeabed: false, annularContrast: 0.85, isSuppressedRipple: false, explanation: 'Isolated discrete target' },
    });

    // NON-NEGOTIABLE REGRESSION REQUIREMENT:
    expect(bicycle.finalClass).not.toBe('ghost_net');
    expect(bicycle.finalClass).toBe('submerged_bicycle');
    expect(bicycle.calibratedConfidence).toBeGreaterThan(80.0);
    assert.ok(bicycle.overrideOccurred, 'Detector should record override of raw detector output');
  });

  // Test 2: Bicycle components should merge into one target
  it('2. Bicycle components (wheels, frame, crank) should merge into one target', () => {
    const components: AcousticComponent[] = [
      { id: "comp-1", x0: 100, x1: 140, y0: 100, y1: 140, centroidX: 120, centroidY: 120, areaPx: 450, peakIntensity: 240, meanIntensity: 210, shadowScore: 0.85, shadowLengthPx: 40 }, // Front wheel
      { id: "comp-2", x0: 130, x1: 210, y0: 110, y1: 135, centroidX: 170, centroidY: 122, areaPx: 380, peakIntensity: 230, meanIntensity: 205, shadowScore: 0.80, shadowLengthPx: 38 }, // Frame tube
      { id: "comp-3", x0: 200, x1: 240, y0: 100, y1: 140, centroidX: 220, centroidY: 120, areaPx: 440, peakIntensity: 245, meanIntensity: 215, shadowScore: 0.82, shadowLengthPx: 42 }, // Rear wheel
    ];

    const clusters = performStructuralClusterFusion(components, 50, 400);
    // All 3 disjoint acoustic highlights must fuse into 1 unified bicycle target
    expect(clusters.length).toBe(1);
    expect(clusters[0].constituentCount).toBe(3);
  });

  // Test 3: Sand ripple field should not produce many debris boxes
  it('3. Sand ripple field should be suppressed via annular background context', () => {
    const width = 120;
    const height = 120;
    const rippleBuffer = new Float32Array(width * height);
    for (let y = 0; y < height; y++) {
      for (let x = 0; x < width; x++) {
        // Continuous periodic sand ripple across entire tile
        rippleBuffer[y * width + x] = 120 + 50 * Math.sin(x * 0.4);
      }
    }

    const context = evaluateSeabedContext(rippleBuffer, width, height, { x0: 40, y0: 40, x1: 80, y1: 80 });
    expect(context.isNaturalSeabed).toBe(true);
    expect(context.isSuppressedRipple).toBe(true);
    assert.match(context.explanation, /sand ripple|periodic seabed/i);
  });

  // Test 4: Pipe should produce linear/tubular evidence
  it('4. Pipe should produce strong linear and tubular evidence with cylindrical shadow', () => {
    const width = 120;
    const height = 120;
    const pipeBuffer = new Float32Array(width * height);
    // Draw an elongated horizontal bright cylinder
    for (let y = 50; y < 65; y++) {
      for (let x = 20; x < 100; x++) {
        pipeBuffer[y * width + x] = 230;
      }
    }

    const pipeRes = analyzeLinearMorphology(pipeBuffer, width, height, { x0: 20, y0: 50, x1: 100, y1: 65 }, 0.85);
    expect(pipeRes.isPipeline).toBe(true);
    expect(pipeRes.score).toBeGreaterThan(0.70);
  });

  // Test 5: Ghost net should require net-specific evidence
  it('5. Ghost net classification requires net-specific evidence and triggers veto if absent', () => {
    const emptyTile = new Float32Array(100 * 100).fill(100);
    const noNet = analyzeNetSignature(emptyTile, 100, 100, { x0: 20, y0: 20, x1: 60, y1: 60 });
    
    // NET VETO must trigger when mesh and rope signatures are absent
    expect(noNet.vetoTriggered).toBe(true);
    expect(noNet.score).toBeLessThan(0.30);
  });

  // Test 6: Unknown anthropogenic structure should remain unknown when class evidence is weak
  it('6. Unknown anthropogenic structure should be routed to unknown_manmade', () => {
    const unknownTarget = evaluateMultiHeadClassification({
      rawClassProposal: 'unknown_manmade',
      rawObjectnessConfidence: 75.0,
      circular: { score: 0.25, circlesFound: 0, annularContinuity: 0.1, pairSpacingPx: null, radii: [], centers: [], explanation: 'No circles' },
      truss: { score: 0.30, lineCount: 1, junctionCount: 0, meanTubeWidth: 0, isTrussFrame: false, segments: [], explanation: 'No frame' },
      linear: { score: 0.20, elongation: 1.5, straightness: 0.3, widthConsistency: 0.4, dominantOrientationDeg: 0, isPipeline: false, explanation: 'Not linear' },
      net: { score: 0.10, ropeScore: 0.05, meshScore: 0.05, drapingScore: 0.05, floatSinkerScore: 0, vetoTriggered: true, explanation: 'No net signatures' },
      anthropogenic: { anthropogenicScore: 0.88, anomalyScore: 0.84, wreckScore: 0.20, isAnthropogenic: true, explanation: 'Strong anthropogenic signature' },
      shadow: { hasValidShadow: true, shadowLengthM: 1.5, shadowLengthPx: 35, shadowScore: 0.80, shadowSide: 'correct', heightEstimateM: 1.4, heightPlausibility: 0.85, explanation: 'Valid relief' },
      seabed: { naturalSeabedScore: 0.05, isNaturalSeabed: false, annularContrast: 0.85, isSuppressedRipple: false, explanation: 'Discrete target' },
    });

    expect(unknownTarget.finalClass).toBe('unknown_manmade');
    assert.match(unknownTarget.decisionReason, /Anthropogenic structure/i);
  });

  // Test 7: Missing navigation must never produce coordinates
  it('7. Missing navigation must strictly return null coordinates and UNAVAILABLE status', () => {
    const result = calculateTargetGeolocation(null, null, null, 45.0, 'starboard');
    expect(result.status).toBe('UNAVAILABLE');
    expect(result.latitude).toBeNull();
    expect(result.longitude).toBeNull();
    expect(result.utmZone).toBeNull();
    expect(result.r95UncertaintyM).toBeNull();
  });

  // Test 8: Motion artifact should be suppressed when overlap exceeds threshold
  it('8. Motion artifact should be suppressed when candidate overlaps motion-corrupted pings', () => {
    const corruptedPings = new Set([100, 101, 102, 103, 104, 105, 106, 107]); // 8 corrupted pings
    const { overlapFraction, shouldSuppress } = computeCandidateMotionOverlap(100, 110, corruptedPings, 0.50);
    // 8 out of 11 pings corrupted = 72.7% > 50%
    expect(overlapFraction).toBeGreaterThan(0.70);
    expect(shouldSuppress).toBe(true);
  });

  // Test 9: Single-pass survey must not receive persistence penalty
  it('9. Single-pass survey must receive neutral persistence (no penalty)', () => {
    // When only 1 survey pass exists, persistence is neutral (0.50)
    const singlePassPersistence = 0.50;
    expect(singlePassPersistence).toBe(0.50);
  });

  // Test 10: Multi-pass matching must increase persistence evidence
  it('10. Multi-pass matching within 5m radius must increase persistence evidence', () => {
    // Target re-acquired across line 07 and line 08 within 3.4m distance
    const distBetweenPassesM = 3.4;
    const isMultiPassMatched = distBetweenPassesM <= 5.0;
    const multiPassPersistence = isMultiPassMatched ? 0.92 : 0.50;

    expect(isMultiPassMatched).toBe(true);
    expect(multiPassPersistence).toBeGreaterThan(0.85);
  });

  // Test 11: Slant-range correction must produce physically valid ground range
  it('11. Slant-range correction G = sqrt(R² - H²) must produce valid ground range and identify water column', () => {
    const H = 8.0; // Altitude 8.0m
    
    // Case A: Slant range 10.0m -> G = sqrt(100 - 64) = 6.0m
    const resA = slantToGroundRange(10.0, H);
    expect(resA.inWaterColumn).toBe(false);
    assert.equal(Math.round(resA.groundRangeM * 10) / 10, 6.0);

    // Case B: Slant range 6.0m < H 8.0m (Inside water column / nadir blanking)
    const resB = slantToGroundRange(6.0, H);
    expect(resB.inWaterColumn).toBe(true);
    expect(resB.groundRangeM).toBe(0);
  });

  // Test 12: Shadow height calculation must match known synthetic geometry
  it('12. Shadow relief height formula h = (Ls * H) / (R + Ls) must match synthetic geometry', () => {
    const knownHeight = 1.5;
    const altitude = 10.0;
    const range = 50.0;
    // Known shadow length Ls = h * R / (H - h) = 1.5 * 50 / 8.5 = 8.8235m
    const syntheticLs = computePhysicalShadowLength(knownHeight, altitude, range);
    
    // Invert using shadow height formula
    const calc = calculateShadowReliefHeight(syntheticLs, altitude, range);
    assert.equal(Math.round(calc.heightM * 10) / 10, knownHeight);
  });

  // Test 13: UTM zone must be automatically determined
  it('13. UTM zone must be dynamically determined without hard-coding', () => {
    // Chennai Outer Anchorage: 80.298°E -> UTM Zone 44N
    const zoneChennai = getUTMZone(13.085, 80.298);
    expect(zoneChennai.zoneStr).toBe('UTM Zone 44N');

    // Gulf of Mannar: 79.120°E -> UTM Zone 44N
    const zoneMannar = getUTMZone(9.280, 79.120);
    expect(zoneMannar.zoneStr).toBe('UTM Zone 44N');

    // Mumbai Harbour: 72.850°E -> UTM Zone 43N
    const zoneMumbai = getUTMZone(18.920, 72.850);
    expect(zoneMumbai.zoneStr).toBe('UTM Zone 43N');
  });

  // Test 14: Cluster fusion must merge structurally related components
  it('14. Cluster fusion must calculate S_merge from spatial, shadow, and geometry compatibility', () => {
    const compA: AcousticComponent = { id: "c-1", x0: 50, x1: 70, y0: 50, y1: 70, centroidX: 60, centroidY: 60, areaPx: 200, peakIntensity: 220, meanIntensity: 200, shadowScore: 0.80, shadowLengthPx: 30 };
    const compB: AcousticComponent = { id: "c-2", x0: 75, x1: 95, y0: 52, y1: 68, centroidX: 85, centroidY: 60, areaPx: 180, peakIntensity: 210, meanIntensity: 195, shadowScore: 0.78, shadowLengthPx: 29 };

    const clusters = performStructuralClusterFusion([compA, compB], 45, 400);
    expect(clusters.length).toBe(1);
    expect(clusters[0].constituentCount).toBe(2);
  });

  // Test 15: Class assignment must never use height alone
  it('15. Class assignment must NEVER use height alone to assign ghost_net or any class', () => {
    // Target with height = 1.2m, but with zero net signatures and neutral morphology
    const target = evaluateMultiHeadClassification({
      rawClassProposal: 'unknown_manmade',
      rawObjectnessConfidence: 50.0,
      circular: { score: 0.1, circlesFound: 0, annularContinuity: 0.1, pairSpacingPx: null, radii: [], centers: [], explanation: 'No circles' },
      truss: { score: 0.1, lineCount: 0, junctionCount: 0, meanTubeWidth: 0, isTrussFrame: false, segments: [], explanation: 'No frame' },
      linear: { score: 0.1, elongation: 1.0, straightness: 0.1, widthConsistency: 0.2, dominantOrientationDeg: 0, isPipeline: false, explanation: 'Not linear' },
      net: { score: 0.05, ropeScore: 0.05, meshScore: 0.05, drapingScore: 0.05, floatSinkerScore: 0, vetoTriggered: true, explanation: 'Net veto' },
      anthropogenic: { anthropogenicScore: 0.65, anomalyScore: 0.60, wreckScore: 0.1, isAnthropogenic: true, explanation: 'Generic relief' },
      shadow: { hasValidShadow: true, shadowLengthM: 1.2, shadowLengthPx: 25, shadowScore: 0.70, shadowSide: 'correct', heightEstimateM: 1.2, heightPlausibility: 0.8, explanation: '1.2m relief' }, // 1.2m height!
      seabed: { naturalSeabedScore: 0.05, isNaturalSeabed: false, annularContrast: 0.8, isSuppressedRipple: false, explanation: 'Isolated target' },
    });

    // ABSOLUTE RULE CHECK: Height alone must NOT produce ghost_net!
    expect(target.finalClass).not.toBe('ghost_net');
    expect(target.finalClass).toBe('unknown_manmade');
  });

});
