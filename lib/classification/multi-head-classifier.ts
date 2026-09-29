/**
 * Multi-Head Evidence-Driven Classifier & Open-Set Decision Engine
 * Section 24, 27, 28, 29: Synthesizes evidence across all morphology heads, physics verification,
 * and open-set anomaly detection.
 * 
 * NON-NEGOTIABLE ARCHITECTURAL PRINCIPLES:
 * 1. AI proposes candidates.
 * 2. Sonar morphology determines structural characteristics.
 * 3. Class-specific acoustic signatures verify identity.
 * 4. Physics verifies whether interpretation is physically plausible.
 * 5. Open-set recognition handles previously unseen man-made objects (unknown_manmade).
 * 6. Evidence fusion produces the final result.
 * 7. NEVER assign classes from height alone.
 */

import type { DebrisClass, ComprehensiveEvidence, ClassEvidenceScores } from "../../types/survey.ts";
import type { CircularAnalysisResult } from "../morphology/circular.ts";
import type { TrussAnalysisResult } from "../morphology/truss.ts";
import type { LinearAnalysisResult } from "../morphology/linear.ts";
import type { NetSignatureResult } from "../morphology/net-signature.ts";
import type { AnthropogenicAnalysisResult } from "../morphology/anthropogenic.ts";
import type { ShadowAnalysisResult } from "../physics/shadow.ts";
import type { SeabedContextResult } from "../physics/seabed-context.ts";

export interface ClassificationDecision {
  finalClass: DebrisClass;
  calibratedConfidence: number; // [0, 100]%
  rawClass: DebrisClass;
  rawConfidence: number; // [0, 100]%
  overrideOccurred: boolean;
  overrideLog: string | null;
  decisionReason: string;
  isSuppressed: boolean;
  suppressionReason: string | null;
  comprehensiveEvidence: ComprehensiveEvidence;
  classScores: ClassEvidenceScores;
}

export function evaluateMultiHeadClassification(params: {
  rawClassProposal?: DebrisClass;
  rawObjectnessConfidence?: number;
  circular: CircularAnalysisResult;
  truss: TrussAnalysisResult;
  linear: LinearAnalysisResult;
  net: NetSignatureResult;
  anthropogenic: AnthropogenicAnalysisResult;
  shadow: ShadowAnalysisResult;
  seabed: SeabedContextResult;
  motionQuality?: number; // [0, 1]
  persistence?: number; // [0, 1]
  // REMOVED: hasBikeFileNameHint (Ground Rule 5 — inference must never read filenames)
}): ClassificationDecision {
  const {
    rawClassProposal = "unknown_manmade",
    rawObjectnessConfidence = 0,
    circular,
    truss,
    linear,
    net,
    anthropogenic,
    shadow,
    seabed,
    motionQuality = 0.95,
    persistence = 0.85,
    // hasBikeFileNameHint removed
  } = params;

  // 1. Natural Seabed Suppression Check (Sand ripples, smooth seafloor)
  if (seabed.isSuppressedRipple && !anthropogenic.isAnthropogenic) {
    const classScores: ClassEvidenceScores = {
      net_debris: 0.05,
      wreck: 0.04,
      pipe_cylinder: 0.02,
      other_manmade: 0.05,
      unknown_manmade: 0.05,
    };

    const evidence: ComprehensiveEvidence = {
      cnn: rawObjectnessConfidence / 100,
      shadow: shadow.shadowScore,
      height: shadow.heightPlausibility,
      circular: circular.score,
      truss: truss.score,
      tubular: truss.score,
      linear: linear.score,
      mesh: net.meshScore,
      rope: net.ropeScore,
      draping: net.drapingScore,
      floatSinker: net.floatSinkerScore,
      wreckStructure: anthropogenic.wreckScore,
      anthropogenic: anthropogenic.anthropogenicScore,
      anomaly: anthropogenic.anomalyScore,
      motionQuality,
      persistence,
      naturalSeabed: seabed.naturalSeabedScore,
      structuralMerge: 0.5,
    };

    return {
      finalClass: "unknown_manmade",
      calibratedConfidence: 8.5,
      rawClass: rawClassProposal,
      rawConfidence: rawObjectnessConfidence,
      overrideOccurred: true,
      overrideLog: "Candidate rejected: Annular contrast analysis confirms natural continuous sand ripple texture.",
      decisionReason: seabed.explanation,
      isSuppressed: true,
      suppressionReason: "Suppressed: Periodic sand ripple texture continues seamlessly into surrounding seabed.",
      comprehensiveEvidence: evidence,
      classScores,
    };
  }

  // 2. Compute Multi-Class Evidence Scores [0, 1]
  // NOTE: This is the RENDER-ONLY TypeScript path. All real inference is in the Python backend.
  // Scores here are purely for rendering demo data or the legacy in-browser stub.
  //
  // A. Net/Ghost-Net Score: Requires rope, mesh, floats. Height is NOT the decider.
  let netDebrisScore = (
    net.score * 0.65 +
    shadow.shadowScore * 0.20
    // REMOVED: rawClassProposal bonus (was seeding ghost_net with heuristic proposal)
  );
  if (net.vetoTriggered) {
    netDebrisScore = Math.min(0.12, netDebrisScore * 0.2); // Strict net veto
  }

  // REMOVED: submerged_bicycle score (not a trained class; open-set test object → other_manmade)
  // REMOVED: trap_pot score (not in target taxonomy)
  // REMOVED: hasBikeFileNameHint branch (Ground Rule 5)

  // B. Pipeline / Cylinder Score: Requires continuous linear elongation + width consistency
  let pipeScore = (
    linear.score * 0.65 +
    shadow.shadowScore * 0.25
    // REMOVED: rawClassProposal bonus (was seeding with heuristic)
  );

  // C. Wreck Score: Massive structural acoustic mass + high shadow relief
  let wreckScore = (
    anthropogenic.wreckScore * 0.60 +
    shadow.shadowScore * 0.30
    // REMOVED: rawClassProposal bonus
  );

  // D. Other Man-Made (catches trained open-set objects the model knows are anthropogenic
  //    but cannot assign to wreck/pipe/net): bicycle, ladder, cage, etc. route here.
  const otherManmadeScore = Math.min(
    0.95,
    anthropogenic.anthropogenicScore * 0.60 + anthropogenic.anomalyScore * 0.20 + circular.score * 0.10 + truss.score * 0.10
  );

  // E. Unknown Anthropogenic (open-set, never seen man-made class)
  const unknownManmadeScore = Math.min(
    0.98,
    anthropogenic.anthropogenicScore * 0.70 + anthropogenic.anomalyScore * 0.30
  );

  const classScores: ClassEvidenceScores = {
    net_debris: Math.round(netDebrisScore * 100) / 100,
    wreck: Math.round(wreckScore * 100) / 100,
    pipe_cylinder: Math.round(pipeScore * 100) / 100,
    other_manmade: Math.round(otherManmadeScore * 100) / 100,
    unknown_manmade: Math.round(unknownManmadeScore * 100) / 100,
  };

  // 3. Open-Set Multi-Stage Decision (RENDER-ONLY stub — real logic is in Python)
  let finalClass: DebrisClass = "unknown_manmade";
  let confidenceVal = 0.50;
  let decisionReason = "";
  let overrideOccurred = false;
  let overrideLog: string | null = null;

  const KNOWN_CLASS_THRESHOLD = 0.62;

  // Check known classes by evidence specificity
  if (pipeScore >= KNOWN_CLASS_THRESHOLD && pipeScore > netDebrisScore) {
    finalClass = "pipe_cylinder";
    confidenceVal = pipeScore;
    decisionReason = `Pipeline/cylindrical structure: elongation ${linear.elongation}:1, width consistency ${(linear.widthConsistency * 100).toFixed(0)}%.`;
    if (rawClassProposal !== "pipe_cylinder") {
      overrideOccurred = true;
      overrideLog = `Raw proposal (${rawClassProposal}) overridden by linear pipeline morphology.`;
    }
  } else if (netDebrisScore >= KNOWN_CLASS_THRESHOLD && !net.vetoTriggered) {
    finalClass = "net_debris";
    confidenceVal = netDebrisScore;
    decisionReason = `Net debris: rope ${(net.ropeScore * 100).toFixed(0)}%, mesh ${(net.meshScore * 100).toFixed(0)}%, floats ${(net.floatSinkerScore * 100).toFixed(0)}%.`;
  } else if (wreckScore >= KNOWN_CLASS_THRESHOLD) {
    finalClass = "wreck";
    confidenceVal = wreckScore;
    decisionReason = `Wreck debris: large structural acoustic return with complex relief shadow.`;
  } else if (otherManmadeScore >= KNOWN_CLASS_THRESHOLD && anthropogenic.isAnthropogenic) {
    // Open-set trained objects (bicycle, ladder, cage etc.) route here
    finalClass = "other_manmade";
    confidenceVal = otherManmadeScore;
    decisionReason = `Other man-made object: demonstrably anthropogenic geometry but no known trained class matches. Recommend ROV inspection.`;
    if (rawClassProposal !== "other_manmade") {
      overrideOccurred = true;
      overrideLog = `Raw proposal (${rawClassProposal}) insufficient; routed to other_manmade.`;
    }
  } else if (anthropogenic.isAnthropogenic) {
    finalClass = "unknown_manmade";
    confidenceVal = unknownManmadeScore;
    decisionReason = `Unknown anthropogenic: acoustic reflectivity confirms man-made but no class evidence is sufficient. Recommend ROV inspection.`;
    if (rawClassProposal !== "unknown_manmade") {
      overrideOccurred = true;
      overrideLog = `Proposal (${rawClassProposal}) rejected: insufficient evidence for a known class.`;
    }
  } else {
    finalClass = "unknown_manmade";
    confidenceVal = 0.38;
    decisionReason = `Low structural confidence: acoustic return lacks definitive man-made geometry.`;
  }

  // 4. Final Calibrated Confidence: Fused with motion quality and persistence
  const calibratedConfidence = Math.round(
    Math.min(99, Math.max(10, (confidenceVal * 0.75 + motionQuality * 0.15 + persistence * 0.10) * 100)) * 10
  ) / 10;

  const isSuppressed = calibratedConfidence < 35 || shadow.shadowSide === "incorrect";
  const suppressionReason = isSuppressed
    ? shadow.shadowSide === "incorrect"
      ? "Anti-causal shadow points toward nadir (depression, not a raised hazard)."
      : "Calibrated hazard confidence below operational reporting threshold (35%)."
    : null;

  const evidence: ComprehensiveEvidence = {
    cnn: rawObjectnessConfidence / 100,
    shadow: shadow.shadowScore,
    height: shadow.heightPlausibility,
    circular: circular.score,
    truss: truss.score,
    tubular: truss.score,
    linear: linear.score,
    mesh: net.meshScore,
    rope: net.ropeScore,
    draping: net.drapingScore,
    floatSinker: net.floatSinkerScore,
    wreckStructure: anthropogenic.wreckScore,
    anthropogenic: anthropogenic.anthropogenicScore,
    anomaly: anthropogenic.anomalyScore,
    motionQuality,
    persistence,
    naturalSeabed: seabed.naturalSeabedScore,
    structuralMerge: 0.94,
  };

  return {
    finalClass,
    calibratedConfidence,
    rawClass: rawClassProposal,
    rawConfidence: rawObjectnessConfidence,
    overrideOccurred,
    overrideLog,
    decisionReason,
    isSuppressed,
    suppressionReason,
    comprehensiveEvidence: evidence,
    classScores,
  };
}
