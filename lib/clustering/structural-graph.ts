/**
 * Structural Component Extraction & Proximity Fusion Engine
 * Section 10 & 11: Fixes target fragmentation (e.g. bicycle split into separate wheels, pedals, and tubes).
 * Implements graph-based structural grouping across disjoint acoustic echoes sharing the same
 * physical spatial envelope, down-range acoustic shadow, and structural geometry.
 */

export interface AcousticComponent {
  id: string;
  x0: number;
  y0: number;
  x1: number;
  y1: number;
  centroidX: number;
  centroidY: number;
  areaPx: number;
  peakIntensity: number;
  meanIntensity: number;
  shadowScore: number;
  shadowLengthPx: number;
}

export interface MergedPhysicalTarget {
  id: string;
  bbox: { x0: number; y0: number; x1: number; y1: number };
  widthPx: number;
  heightPx: number;
  centroidX: number;
  centroidY: number;
  totalAreaPx: number;
  constituentCount: number;
  constituentIds: string[];
  shadowScore: number;
  shadowLengthPx: number;
  mergeConfidence: number; // S_merge score
  structuralTypeGuess?: string;
}

export function performStructuralClusterFusion(
  components: AcousticComponent[],
  proximityPxThreshold: number = 42,
  nadirX: number = 400
): MergedPhysicalTarget[] {
  if (components.length === 0) return [];
  if (components.length === 1) {
    const c = components[0];
    return [{
      id: "TGT-001",
      bbox: { x0: c.x0, y0: c.y0, x1: c.x1, y1: c.y1 },
      widthPx: c.x1 - c.x0,
      heightPx: c.y1 - c.y0,
      centroidX: c.centroidX,
      centroidY: c.centroidY,
      totalAreaPx: c.areaPx,
      constituentCount: 1,
      constituentIds: [c.id],
      shadowScore: c.shadowScore,
      shadowLengthPx: c.shadowLengthPx,
      mergeConfidence: 1.0,
    }];
  }

  // Build Adjacency Graph based on S_merge
  const n = components.length;
  const adj: number[][] = Array.from({ length: n }, () => []);

  for (let i = 0; i < n; i++) {
    for (let j = i + 1; j < n; j++) {
      const c1 = components[i];
      const c2 = components[j];

      // 1. Spatial distance between bounding boxes
      const dx = Math.max(0, Math.max(c1.x0 - c2.x1, c2.x0 - c1.x1));
      const dy = Math.max(0, Math.max(c1.y0 - c2.y1, c2.y0 - c1.y1));
      const edgeDist = Math.hypot(dx, dy);

      // Spatial similarity [0, 1]
      const spatialSim = Math.max(0, 1 - edgeDist / (proximityPxThreshold * 1.5));

      // 2. Down-range Shadow Similarity
      // If two components cast shadows pointing in the same direction with similar lengths, they are part of the same object
      const isStarboard1 = c1.centroidX >= nadirX;
      const isStarboard2 = c2.centroidX >= nadirX;
      const shadowDirectionMatch = isStarboard1 === isStarboard2 ? 1.0 : 0.0;
      const shadowLengthDiff = Math.abs(c1.shadowLengthPx - c2.shadowLengthPx);
      const shadowSim = shadowDirectionMatch * Math.max(0, 1 - shadowLengthDiff / 60);

      // 3. Range compatibility (same survey line / ping interval overlap)
      const yOverlap = Math.min(c1.y1, c2.y1) - Math.max(c1.y0, c2.y0);
      const rangeCompat = yOverlap > -30 ? 1.0 : 0.4;

      // S_merge = wd * spatial + ws * shadow + wg * range
      const sMerge = 0.50 * spatialSim + 0.30 * shadowSim + 0.20 * rangeCompat;

      // Merge threshold: default >= 0.52 or edge distance within configured proximity
      if (sMerge >= 0.48 || edgeDist <= proximityPxThreshold) {
        adj[i].push(j);
        adj[j].push(i);
      }
    }
  }

  // Connected Component Decomposition on the Graph
  const visited = new Uint8Array(n);
  const targetGroups: number[][] = [];

  for (let i = 0; i < n; i++) {
    if (!visited[i]) {
      const group: number[] = [];
      const queue: number[] = [i];
      visited[i] = 1;

      while (queue.length > 0) {
        const curr = queue.shift()!;
        group.push(curr);

        for (const neighbor of adj[curr]) {
          if (!visited[neighbor]) {
            visited[neighbor] = 1;
            queue.push(neighbor);
          }
        }
      }
      targetGroups.push(group);
    }
  }

  // Synthesize Unified Physical Targets
  const mergedTargets: MergedPhysicalTarget[] = targetGroups.map((group, idx) => {
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    let totalArea = 0;
    let maxShadowScore = 0;
    let maxShadowLength = 0;
    let sumWeightX = 0, sumWeightY = 0;

    for (const cIdx of group) {
      const c = components[cIdx];
      minX = Math.min(minX, c.x0);
      minY = Math.min(minY, c.y0);
      maxX = Math.max(maxX, c.x1);
      maxY = Math.max(maxY, c.y1);
      totalArea += c.areaPx;
      if (c.shadowScore > maxShadowScore) maxShadowScore = c.shadowScore;
      if (c.shadowLengthPx > maxShadowLength) maxShadowLength = c.shadowLengthPx;
      sumWeightX += c.centroidX * c.areaPx;
      sumWeightY += c.centroidY * c.areaPx;
    }

    const centroidX = totalArea > 0 ? Math.round(sumWeightX / totalArea) : Math.round((minX + maxX) / 2);
    const centroidY = totalArea > 0 ? Math.round(sumWeightY / totalArea) : Math.round((minY + maxY) / 2);

    return {
      id: `TGT-${String(idx + 1).padStart(3, "0")}`,
      bbox: { x0: minX, y0: minY, x1: maxX, y1: maxY },
      widthPx: maxX - minX,
      heightPx: maxY - minY,
      centroidX,
      centroidY,
      totalAreaPx: totalArea,
      constituentCount: group.length,
      constituentIds: group.map((i) => components[i].id),
      shadowScore: maxShadowScore,
      shadowLengthPx: maxShadowLength,
      mergeConfidence: group.length > 1 ? 0.94 : 1.0,
      structuralTypeGuess: group.length >= 2 ? "Multi-component framework assembly" : "Isolated target",
    };
  });

  return mergedTargets;
}
