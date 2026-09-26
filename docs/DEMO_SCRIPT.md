# SagarNetra: Demonstration Script for SIH 2026 Judges
**Problem Statement 26057: Automated Underwater Marine Debris & Anomaly Detection Using Side-Scan Sonar**  
**Host Organization:** National Institute of Ocean Technology (NIOT), Ministry of Earth Sciences (MoES)  
**Presenter:** SagarNetra Engineering Team  
**Estimated Demo Time:** 8–10 Minutes  
**System Architecture:** Real-Data-First Production Prototype

---

## 1. Executive Hook: Real-Data-First Decision Support (Minute 0:00 – 1:00)

> **"Respected Judges, Scientists of NIOT and MoES:**  
> Many teams approach this challenge as a simple AI computer-vision classification task: download shipwreck photos or crab-pot images, run generic YOLO, and draw bounding boxes on a screen.
> 
> When deployed on an actual hydrographic survey vessel, that paradigm fails immediately:
> 1. **Data Honesty:** There is **no public real ghost-net side-scan sonar dataset** anywhere in the world. Claiming a crab-pot is a ghost net or claiming synthetic imagery is field data is physically and scientifically incorrect.
> 2. **Acoustic Physics:** A ghost net draped over the seafloor has low backscatter and faint shadows; rock ridges and sand waves look identical to generic neural networks.
> 3. **Actionable Operations:** A diver or ROV cannot dive on raw pixel bounding boxes without acoustic height, geodetic coordinates, and an honest $r_{95}$ positioning ellipse.
> 
> We built **SagarNetra** under a strict **REAL-DATA-FIRST** principle:
> - **REAL DATA = PRIMARY**: Direct ingestion of real raw hydrographic surveys (XTF, NOAA, USGS, KLSG-II, AI4Shipwrecks, GhostPot, SCTD) for detection, bottom tracking, georeferencing, and evaluation.
> - **HYBRID DATA = SECONDARY**: Injects physics-simulated nets into real seafloor backgrounds exclusively to bridge the ghost-net training gap.
> - **PURE SIMULATION = TERTIARY**: SonarForge is preserved as a controlled engineering tool for PoD sweeps and acoustic stress testing.
> - **INDIAN DATA HONESTY**: If permitted Indian survey data is not yet loaded, we explicitly state *'REAL INDIAN FIELD DATA NOT LOADED'*—we never fabricate Indian field records.
> 
> SagarNetra runs 100% offline at the edge, outputs real physical dimensions in metres, verifies detections with 8 acoustic physics rules, and proves which sectors of the seabed are cleared."

---

## 2. The Primary Demonstration: Real Hydrographic Survey Workflow (Minute 1:00 – 5:30)

### Step 1: Open SagarNetra & Ingest Real Survey
* **Screen:** [Mission Control](file:///d:/SIHPS2/frontend/index.html)
* **What to Show:**
  1. Click the **Data Provenance** button in the top navigation bar to open the **Dataset Provenance & Quality Status** modal:
     - Show the real datasets registry: `GhostPot (CC-BY-4.0)`, `AI4Shipwrecks (MIT)`, `KLSG-II (CC-BY-4.0)`, `SCTD2`, `NOAA NCEI/USGS`.
     - Point out the status badge: <span style="color:#FFA502">**INDIAN DATA: PENDING PERMITTED IMPORT**</span>. We do not invent fake Indian data.
     - Point out the field validation badge: <span style="color:#2ED573">**REAL GHOST NET FIELD STATUS: PENDING VERIFIED FIELD DATA**</span>.
  2. In the **Mission Control** Real Hydrographic Survey Ingestion Strip, select:
     - `NOAA Survey H13112 (EdgeTech 4200, 400 kHz, 75 m Range)`
  3. Click **LOAD REAL SURVEY**:
     - Observe the parsed metadata: Sensor: `EdgeTech 4200`, Frequency: `400 kHz`, Range: `75.0 m`, Navigation: `WGS-84 / UTM Zone 18N`.
     - Ping Quality check runs: `0 missing pings`, `0 zero-energy pings`, `0 altitude jumps`.

### Step 2: Real Preprocessing & Waterfall Streaming
* **What to Show:**
  1. Click **START ANALYSIS**:
     - The waterfall activates in **REPLAY** mode (reflecting deterministic recorded pings, not fake live telemetry).
     - Show port, nadir water-column blank, and starboard swaths.
     - Point out real-time bottom tracking locked onto the true seafloor return.

### Step 3: Candidate Detection & Layered Evidence Inspection
* **Screen:** [Target Inspector](file:///d:/SIHPS2/frontend/index.html)
* **What to Show:**
  1. A real shipwreck debris candidate `TGT-00017` is flagged by the OS-CFAR detector.
  2. Click `TGT-00017` to inspect real acoustic evidence:
     - Note the badge: **SOURCE: REAL** (AI4Shipwrecks / NOAA held-out split).
     - Cycle through the **Multi-Layer Toggle Bar**:
       - `[RAW]` -> Unprocessed raw backscatter pings.
       - `[NORMALIZED]` -> Slant-range corrected and TVG gain compensated.
       - `[DESPECKLED]` -> Lee filter speckle-suppressed.
       - `[SHADOW]` -> Acoustic shadow probability map.
       - `[RIDGE]` -> Matched-filter structural ridge response.
       - `[MASK]` -> Ground-truth / predicted segmentation outline.
       - `[PHYSICS]` -> Acoustic ray overlay showing ray path from towfish altitude ($H = 12.4\text{ m}$) to shadow tip.
  3. Show the **Acoustic Dimension & Height Calculation**:
     $$h = H \cdot \frac{L_s}{x_0 + L_s} = 12.4 \cdot \frac{8.2}{24.6 + 8.2} = 3.1\text{ m}$$
     $$\text{Length: } 18.4\text{ m}, \quad \text{Width: } 6.2\text{ m}$$
  4. Point out the **Honest Navigation & $r_{95}$ Geotag**:
     $$\text{Target Position: } 41.284210^\circ\text{N}, -71.954200^\circ\text{W} \quad (r_{95} = \pm 1.82\text{ m})$$
     - If navigation metadata were absent, SagarNetra would display `GEOLOCATION UNAVAILABLE (Missing navigation metadata)` rather than fabricating coordinates.
  5. Review the **8-Rule Physics Verifier Table (R1–R8)**:
     - Rules R1 through R8 all pass ($V_{phys} = 0.94$).
  6. Operator clicks **CONFIRM** to approve the target for operational clearance.

---

## 3. Secondary Demonstration: Hybrid Ghost-Net Detection (Minute 5:30 – 7:00)

### Addressing the Global Ghost Net Data Scarcity Bottleneck
* **Screen:** [Target Inspector](file:///d:/SIHPS2/frontend/index.html)
* **What to Show:**
  1. Select target `TGT-00001` (Class: `ghost_net`).
  2. Notice the explicit provenance badge: **SOURCE: HYBRID (Real Seafloor + Physics-Simulated Net)**.
  3. Explain the architecture:
     - Real side-scan seabed texture from NOAA/KLSG-II serves as the base layer.
     - A physics-grounded net with known catenary draping, acoustic transparency ($\alpha = 0.42$), and shadow geometry is injected.
  4. Demonstrate the **Net Signature Head**:
     - `S_net = 0.88` based on:
       1. LoG point-float detector identifying corkline air floats.
       2. Euclidean Minimum Spanning Tree (MST) proving periodic spacing ($CV < 0.25$).
       3. Gabor filter bank isolating regular diamond mesh backscatter.
  5. Show performance metrics transparency:
     - Ghost-net recall on Hybrid Benchmark: **83.4% @ 2 FA/km²**.
     - Real field validation status: **Pending verified field data** (strictly adhering to scientific honesty).

---

## 4. Coverage, Clearance & Autonomous Second-Look Track (Minute 7:00 – 8:00)

* **Screen:** [Coverage & Clearance](file:///d:/SIHPS2/frontend/index.html)
* **What to Show:**
  1. Open the **Coverage & Clearance** tab.
  2. The clearance grid is computed from the actual survey navigation swath and sensor beam model:
     - <span style="color:#2ED573">**SURVEYED_CLEAR (Green, PoD $\ge 90\%$)**</span>
     - <span style="color:#FFA502">**ADEQUATE (Amber, $75\% \le \text{PoD} < 90\%$)**</span>
     - <span style="color:#FF4757">**INSUFFICIENT (Red, $\text{PoD} < 75\%$)**</span>
  3. Click on an **INSUFFICIENT** cell:
     - System explains: *'Low grazing angle / nadir altitude jump reduced detection probability below operational threshold.'*
     - SagarNetra does not claim an area is clear simply because no AI box was generated.
  4. Click **GENERATE SECOND-LOOK TRACK**:
     - Generates an optimal infill survey line with target offset at 30–60% of sonar range.
     - Exports as **GeoJSON** and **GPX** for direct upload to vessel ECDIS / autopilot.

---

## 5. Secondary Engineering Tool: SonarForge Lab (Minute 8:00 – 8:45)

* **Screen:** [SonarForge Lab](file:///d:/SIHPS2/frontend/index.html)
* **What to Show:**
  1. Note the prominent header: **SIMULATION / SECONDARY BENCHMARK**.
  2. Demonstrate how SonarForge is used for controlled acoustic engineering:
     - Vary grazing angle, seafloor roughness, and net burial depth ($0\% \to 60\%$).
     - Observe how the synthetic waterfall and PoD curve update in real time.
     - Reiterate: SonarForge is a scientific tool for stress testing and hybrid training generation, never substituted for real field data.

---

## 6. Disaster Mode & Dive-Ready Work Orders (Minute 8:45 – 10:00)

* **Screen:** [Disaster Mode](file:///d:/SIHPS2/frontend/index.html) & [Reports](file:///d:/SIHPS2/frontend/index.html)
* **What to Show:**
  1. In **Disaster Mode**, load baseline survey and post-event survey:
     - Shows sub-pixel phase correlation registration.
     - Identifies **NEW_OBSTRUCTION** deposited in navigation channel.
  2. Switch to **Reports & Work Orders**:
     - Click **Export JSON**, **Export CSV**, **Export GeoJSON**, **Export KML**, and **Download PDF Work Order**.
     - Display the generated PDF / CSV:
       - Shows survey ID, sensor, processing version.
       - Every record has explicit `source_type` (`real`, `hybrid`, `sim`).
       - Geotags, $r_{95}$, physical dimensions, and physics rule results are fully populated with zero hardcoded values.

---

## 7. Summary of Differentiators

| Capability | Standard Vision Submissions | SagarNetra (Real-Data-First Prototype) |
|---|---|---|
| **Data Provenance** | Mixes synthetic and real data indiscriminately | **Strict 3-Tier Provenance**: Real, Hybrid, Sim tracked across every tile, detection, and report |
| **Indian Data Integrity** | Claims fake local deployment | **Absolute Honesty**: Explicitly flags *'REAL INDIAN FIELD DATA NOT LOADED'* until permitted import |
| **Ghost Net Detection** | Fails on thin, low-backscatter netting | **Net Signature Head** (LoG float chains + MST + Gabor) trained on hybrid physics injections |
| **Acoustic Physics** | Blind bounding boxes | **8 Physics Rules (R1–R8)** verifying shadow geometry, ray tracing, and aspect ratio |
| **Physical Measurements**| None | Analytic ray tracing: $h = H \cdot L_s / (x_0 + L_s)$ with sub-decimetre precision |
| **Geotagging & r95** | Raw pixel coordinates or vessel GPS | Catenary towfish layback + UTM projection + honest $r_{95}$ error budget |
| **Deployment** | Requires cloud connection | **100% Offline Edge Operation** on survey laptop / Jetson |
