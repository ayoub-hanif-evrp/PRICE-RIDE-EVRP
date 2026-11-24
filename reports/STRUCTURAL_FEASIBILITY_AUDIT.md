# Structural feasibility on original Porto inputs

Contract porto-v4-conservative-v2. Two physical LEC stations, each with one fleet-wide visit. All 20 files have 40.25 kWh initially and at the reserve, 57.5 kWh capacity, and zero travel from each assigned origin to its unused-route destination. Matrix zeros between different node IDs are retained. Held-out entries use inputs only.

| Instance | N | K | Initial / reserve / cap (kWh) | Sites / visits | Active cap | Purchase upper (kWh) | Travel bounds (min) | Concurrent lower | Status |
|---|---:|---:|---|---|---:|---:|---:|---:|---|
| r2-20 | 20 | 2 | 40.25 / 40.25 / 57.50 | 2 / 2 | 2 | 115.000 | 86.0–1277.8 | 1 | verified feasible |
| rF2-20 | 20 | 2 | 40.25 / 40.25 / 57.50 | 2 / 2 | 2 | 115.000 | 86.0–1277.8 | 1 | verified feasible |
| r4-40 | 40 | 4 | 40.25 / 40.25 / 57.50 | 2 / 2 | 2 | 115.000 | 131.7–1277.8 | 1 | verified feasible |
| rF4-40 | 40 | 4 | 40.25 / 40.25 / 57.50 | 2 / 2 | 2 | 115.000 | 131.4–1277.8 | 1 | verified feasible |
| r6-60 | 60 | 6 | 40.25 / 40.25 / 57.50 | 2 / 2 | 2 | 115.000 | 146.5–1277.8 | 1 | verified feasible |
| rF6-60 | 60 | 6 | 40.25 / 40.25 / 57.50 | 2 / 2 | 2 | 115.000 | 146.3–1277.8 | 1 | verified feasible |
| r8-80 | 80 | 8 | 40.25 / 40.25 / 57.50 | 2 / 2 | 2 | 115.000 | 175.8–1277.8 | 1 | verified feasible |
| rF8-80 | 80 | 8 | 40.25 / 40.25 / 57.50 | 2 / 2 | 2 | 115.000 | 175.6–1277.8 | 1 | verified feasible |
| r10-100 | 100 | 10 | 40.25 / 40.25 / 57.50 | 2 / 2 | 2 | 115.000 | 187.2–1277.8 | 1 | unresolved |
| rF10-100 | 100 | 10 | 40.25 / 40.25 / 57.50 | 2 / 2 | 2 | 115.000 | 186.6–1277.8 | 1 | unresolved |
| r12-120 | 120 | 12 | 40.25 / 40.25 / 57.50 | 2 / 2 | 2 | 115.000 | 199.8–1277.8 | 1 | unresolved |
| rF12-120 | 120 | 12 | 40.25 / 40.25 / 57.50 | 2 / 2 | 2 | 115.000 | 199.8–1277.8 | 1 | unresolved |
| r14-140 | 140 | 14 | 40.25 / 40.25 / 57.50 | 2 / 2 | 2 | 115.000 | 213.9–1277.8 | 1 | unresolved |
| rF14-140 | 140 | 14 | 40.25 / 40.25 / 57.50 | 2 / 2 | 2 | 115.000 | 213.9–1277.8 | 1 | unresolved |
| r16-160 | 160 | 16 | 40.25 / 40.25 / 57.50 | 2 / 2 | 2 | 115.000 | 224.7–1277.8 | 1 | unresolved |
| rF16-160 | 160 | 16 | 40.25 / 40.25 / 57.50 | 2 / 2 | 2 | 115.000 | 224.7–1277.8 | 1 | unresolved |
| r18-180 | 180 | 18 | 40.25 / 40.25 / 57.50 | 2 / 2 | 2 | 115.000 | 231.7–1277.8 | 2 | unresolved |
| rF18-180 | 180 | 18 | 40.25 / 40.25 / 57.50 | 2 / 2 | 2 | 115.000 | 231.7–1277.8 | 2 | unresolved |
| r20-200 | 200 | 20 | 40.25 / 40.25 / 57.50 | 2 / 2 | 2 | 115.000 | 243.8–1277.8 | 2 | unresolved |
| rF20-200 | 200 | 20 | 40.25 / 40.25 / 57.50 | 2 / 2 | 2 | 115.000 | 243.8–1277.8 | 2 | unresolved |

## Derivation

At the reserve a vehicle consuming any positive arc larger than the replay tolerance needs a positive charge. Every such route needs one globally unique station slot. Upper purchase is the sum over slots of the lesser of maximum battery capacity and horizon times rate, with conservative tolerance. Energy balance adds the fleet's initial minus required final energy to give the traction allowance. No depot replenishment is modeled.
Each compulsory passenger node needs an actual incoming arc. Its cheapest eligible predecessor is a lower bound, even when the same predecessor is counted for several nodes. Eligibility relaxes all timing except earliest predecessor completion and latest service at the destination. Directed shortest paths through all nodes, ignoring intermediate service, bound in-vehicle travel. Dividing summed direct lower bounds by maximum capacity gives another fleet travel lower bound.
A mandatory active request cannot travel from any depot through both endpoints and back at zero energy, even in the shortest-path relaxation. The sum of service durations forced into a window divided by its length, rounded up, lower-bounds active vehicles. Strictly overlapping mandatory ride intervals give a capacity bound. An odd cycle in the pair incompatibility graph also needs at least three active vehicles. Each conflict tests all six precedence orders, with relaxed directed arc times and no charge, load, ride limit, or depot restrictions. The JSON records any certifying window, arc, or failed pair sequences.

The triangle audit compares raw directed matrix entries with their shortest-path closure. Closure is for bounds only. Replay and objective use the raw arcs. Status unresolved means no certificate or saved complete witness. See [MODEL_CONTRACT_V2.md](MODEL_CONTRACT_V2.md) for the source scope.
