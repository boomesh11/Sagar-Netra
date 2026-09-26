# SagarNetra-SSS-IN v1 Dataset Card (Real-Data-First Edition)

## 1. Overview & Data Hierarchy
**SagarNetra-SSS-IN v1** is a physics-grounded side-scan sonar (SSS) benchmark dataset designed for automated marine debris, ghost net, and underwater obstruction detection, sizing, and clearance mapping.

### First Principle: Real-Data-First
1. **PRIMARY — Real Sonar Data ($R$)**: Real hydrographic side-scan records and public benchmarks (SCTD, SCTD2, SeabedObjects-KLSG-II, AI4Shipwrecks, Ghost Pot, NOAA/USGS). Real data is the primary source for training, evaluation, and background modeling.
2. **SECONDARY — Hybrid Injected Data ($H$)**: Used exclusively to address the global ghost-net data scarcity bottleneck. Synthetic ghost nets, ropes, and float chains are injected into **real seabed recordings** with matching local $K$-distribution speckle and Poisson-blended boundaries.
3. **TERTIARY — Pure Simulation ($S$)**: SonarForge physics simulator data used exclusively for controlled acoustic experiments, extreme condition stress testing, and reference target PoD calculation. Pure simulation is **never** used as a primary validation benchmark.

> [!IMPORTANT]
> **Ghost Net Data Limitation Statement:**  
> There is currently no verified public side-scan sonar dataset of real ghost nets in Indian or tropical coastal waters. SagarNetra refuses to fabricate field observations or mislabel crab-pot data as ghost nets. Ghost-net performance is reported on hybrid injected benchmarks with the clear statement: *"Real ghost-net field validation: pending verified field data."*

> [!NOTE]
> **Indian Field Survey Status:**  
> The directory `data/real/indian/` is reserved for permitted hydrographic surveys from NIOT/MoES. When no local survey files are present, the system explicitly reports **"REAL INDIAN FIELD DATA NOT LOADED"** rather than generating fabricated field substitutes.

---

## 2. Indian Coastal Seabed Presets

| Preset Name | Geographic Analogue | Seabed Texture | Typical Material | Slope / Roughness |
| :--- | :--- | :--- | :--- | :--- |
| **`EAST_COAST_SAND`** | Chennai, Visakhapatnam shelf | Fine sand with acoustic ripple fields | Sand ($\mu = -27$ dB) | Slope $\le 2.0^\circ$, ripples $0.4\text{--}1.0$ m |
| **`WEST_COAST_MUD`** | Mumbai High, Gulf of Kutch | Flat, soft silt/clay with low backscatter | Mud ($\mu = -35$ dB) | Slope $\le 1.0^\circ$, low relief |
| **`REEF_RUBBLE`** | Gulf of Mannar, Lakshadweep | High-relief coral debris and rock clusters | Rock ($\mu = -17$ dB) | Slope $\le 5.0^\circ$, rocks $0.3\text{--}2.0$ m |
| **`SEAGRASS_BED`** | Palk Bay, Chilika channel | Dense vegetation patches with high variance | Seagrass ($\mu = -25$ dB) | Slope $\le 1.5^\circ$, high texture variance |
| **`HARBOUR_FLOOR`** | Major Port basins (Chennai, Kochi, Vizag)| Silted mud with tyres, chains, blocks | Silt + metal debris | Slope $\le 0.5^\circ$, man-made clutter |

---

## 3. Class Ontology & Label Schema

The dataset uses a 10-class taxonomy: 6 actionable marine debris hazard classes and 4 natural confuser classes (which the AI is trained to recognize and suppress).

### Hazard Classes (Reported)
- **`ghost_net` (0)**: Abandoned gillnets, trammel fragments, draped mesh panels with float chains and footrope sinkers.
- **`rope_cable` (1)**: Abandoned mooring lines, heavy tow cables, derelict wires ($\ge 2$ m).
- **`pipe` (2)**: Exposed underwater pipelines, culverts, drainage conduits ($0.3\text{--}1.2$ m diameter).
- **`cylinder` (3)**: Drums, barrels, spherical floats, mine-like cylindrical casings.
- **`wreck_debris` (4)**: Sunken boat hulls, shipping containers, structural steel fragments.
- **`trap_pot` (5)**: Derelict crab pots, fish cages, wire traps.

### Confuser Classes (Suppressed from Hazard Reports)
- **`rock_cluster` (6)**: Natural boulders, coral heads, acoustic stone mounds.
- **`sand_ripple` (7)**: Periodic sand waveforms and tidal dunes.
- **`seagrass` (8)**: Marine angiosperm patches and seaweed beds.
- **`fish_school` (9)**: Suspended mid-water biomass echoes in the water column.

---

## 4. Feature Representation: 3-Channel Physics Stack

Instead of feeding generic RGB images to the neural network, all tiles are preprocessed into a 3-channel acoustic feature tensor ($512\times 512$ float32 / 8-bit):
- **Channel 0 — Despeckled Intensity**: $7\times 7$ Enhanced Lee filtered normalized acoustic backscatter $[0, 1]$.
- **Channel 1 — Shadow Probability Map**: Local relative darkness map identifying acoustic occlusions cast by elevated objects.
- **Channel 2 — Sato Multi-scale Ridge Filter**: Hessian eigenvalue line detector highlighting headropes, cables, and linear net borders.

---

## 5. Annotation Formats

Each sample provides dual representations:
1. **YOLO Segmentation (`labels/*.txt`)**:
   ```
   <class_id> <x1> <y1> <x2> <y2> ... <xn> <yn>
   ```
   Normalized coordinates in $[0.0, 1.0]$.
2. **Physical Metadata (`meta/*.json`)**:
   ```json
   {
     "sample_id": "sagarnetra_train_east_coast_sand_0001",
     "source": "sim",
     "preset": "EAST_COAST_SAND",
     "object": {
       "class_name": "ghost_net",
       "length_m": 8.5,
       "width_m": 3.0,
       "height_m": 0.45,
       "burial_frac": 0.20,
       "material": "nylon_twine",
       "ground_range_m": 18.2,
       "shadow_length_m": 1.45,
       "altitude_m": 6.0
     }
   }
   ```

---

## 6. Dataset Distribution & Summary

### Class Instance Counts
| Class Name | ID | Total Instances | Fraction |
| :--- | :--- | :--- | :--- |
| `ghost_net` | 0 | 19 | 19.0% |
| `rope_cable` | 1 | 19 | 19.0% |
| `pipe` | 2 | 15 | 15.0% |
| `cylinder` | 3 | 17 | 17.0% |
| `wreck_debris` | 4 | 19 | 19.0% |
| `trap_pot` | 5 | 11 | 11.0% |
| `rock_cluster` | 6 | 0 | - |
| `sand_ripple` | 7 | 0 | - |
| `seagrass` | 8 | 0 | - |
| `fish_school` | 9 | 0 | - |
| **Total** | - | **100** | **100.0%** |

### Split Breakdown
| Split | Images | Fraction |
| :--- | :--- | :--- |
| **`train`** | 60 | 60% |
| **`val`** | 20 | 20% |
| **`test`** | 20 | 20% |
| **Total** | **100** | **100%** |

### Data Sources
| Data Source | Images | Percentage | Type |
| :--- | :--- | :--- | :--- |
| **`sim`** | 50 | 50% | Pure physics simulation (SonarForge ray-casting) |
| **`hybrid`** | 50 | 50% | Physical injection into real/ambient backgrounds with shadow matching |
| **`real`** | 0 | 0% | Real side-scan sonar test logs (external download) |

---

## 7. Licensing & Attribution
- Synthetic scenes generated via SagarNetra SonarForge engine (Apache 2.0).
- Compatible with EdgeTech, Klein, and Humminbird side-scan sonar geometries.
- Intended for Ministry of Earth Sciences (MoES) / NIOT underwater disaster management and ocean cleanup research.
