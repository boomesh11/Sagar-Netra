# SagarNetra Class Mapping Specification (PS 26057)

## Target Taxonomy
The system adheres to the 4 trained target classes defined in the NIOT / MoES problem statement:

1. **`wreck`** (or `wreck_debris`): Sunken hulls, steel superstructures, structural tetrapods, containers.
2. **`pipe_cylinder`**: Exposed or displaced subsea pipelines, steel gas cylinders, oil drums.
3. **`net_debris`**: Abandoned, lost, or discarded fishing gear (ALDFG), gillnets, trawl cod-ends, floatlines.
4. **`other_manmade`**: Crab traps, lobster pots, anchors, chain piles, mooring sinkers.

## Decision Routing Classes
All candidate detections are routed into one of the following decision outputs:
- **`<known_class>`** (`wreck` | `pipe_cylinder` | `net_debris` | `other_manmade`): Candidate passes acoustic highlight-shadow physics, feature morphology, and calibrated confidence thresholds.
- **`unknown_manmade`**: High acoustic impedance anomaly and anthropogenic signature, but low match with trained class priors (e.g. submerged bicycles, ladders, steel shopping carts, held-out open-set clutter).
- **`natural_suppressed`**: Natural seafloor geology (sand ripples, boulders, reef outcroppings, mud mounds) filtered by EchoSift physics and Gabor/FFT texture analysis.
- **`uncertain`**: Insufficient acoustic evidence, acoustic shadow occlusion, or grazing angle distortion.
- **`invalid_input`**: Non-sonar modality (e.g. RGB optical photograph, satellite false-color, atmospheric interference).

## Open-Set Object Mapping
- `submerged_bicycle`: Routed to `unknown_manmade` (or `other_manmade`). Never mapped to `net_debris`.
- `ladder`: Routed to `unknown_manmade` (or `other_manmade`).
- `cage / trap`: Routed to `other_manmade`.
