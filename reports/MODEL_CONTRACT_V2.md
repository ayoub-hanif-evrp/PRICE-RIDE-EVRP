# Porto Phase 2 model contract

Model ID `porto-v4-conservative-v2`. The Phase 1 contract and its evidence are preserved. The same embedded matrix, depot assignment, asset parameters, tariff times and 96-period LEC data are used. Phase 2 introduces a shared search subspace with full station-rate, constant-power sessions and sampled timing. Replay accepts constant rates up to the published bound for an explicit schedule. Both controls and candidate search in that same full-rate subspace. There is no modeled depot energy replenishment.

A new adversarial test reproduced replay accepting a JSON boolean as vehicle ID 1. Vehicle IDs now require an exact integer, like node IDs. This correction leaves all original Phase 1 schedules and results unchanged.

| Topic | Direct evidence | Phase 2 interpretation |
|---|---|---|
| Visit scope and copies | Almeida et al., §3 Experimental Design, Materials and Methods, “Instance file format”, describes a maximum of allowed visits and extra nodes above one. README_v2.txt §6 describes virtual copies. The generator's write_instance header writes 1. In Bresich et al. (2024) §3.1 PDF page 4, and the revisit's §3, a visit cap applies across the fleet in their standard configuration. | Count each visit, including a zero-energy stop, against a global physical-site cap and against the uniqueness of its copy node. The 2026 data article leaves scope implicit. Full resolution requires an author answer. |
| Eligible charge | The 2024 formulation §3.1 and journal revisit §3 require empty vehicles at stations. The Porto article §3 gives power as 22 kW and labels station speed as a maximum. It does not define an aggregate site power constraint or a precise simultaneous-outlet rule. | Empty vehicles only. Phase 2 decodes minimum required energy at maximum rate. A total-slot limit of one already precludes concurrent occupancy at the same official station. Copies in unit tests share a site surplus, without introducing an outlet claim. |
| Price | Almeida et al. §3 “Problem definition and LEC extension” allocates available overproduction at MMR and the rest at grid price. “Electricity tariff construction” also describes MMR as a weighted price. | Allocate finite surplus once per site and interval and apply the embedded MMR to that energy. The grid tariff applies to the remainder. Trade naming and possible blending remain unresolved for external objective comparisons. |
| Service and costs | Almeida et al. §3, including the displayed excess-ride equation, and README §6 use drop service start minus pickup completion minus direct matrix entry. The generator writes legacy weights 0.75/0.25 and distinct EUR/min coefficients 0.36 and 0.31. | Keep signed excess after the existing numerical zero tolerance. Use travel EUR plus user EUR plus energy EUR with no further multiplier. Shortest-path closure is used only for structural lower bounds. |
| Timing and energy | 96 half-open 15-minute periods, with the right edge at 1,440 minutes. File arc times and traction rate define travel energy. | Any waiting or service contributes time but no traction energy. Replay retains the documented 1e-7 absolute time, energy and rate feasibility tolerances. Tiny overhang within the horizon tolerance can clip charged energy billed at 1,440 by less than 1e-7 kWh at the original station rate. Feasible final schedules are independently replayed. |

Sources reviewed. [Porto article](https://pmc.ncbi.nlm.nih.gov/articles/PMC13396958/) · [Zenodo v4 source archive](https://zenodo.org/records/20707207) · [2024 OTF PDF](https://www.honda-ri.de/pubs/pdf/5818.pdf) · [Journal revisit author manuscript](https://www.honda-ri.de/pubs/pdf/6507.pdf)

The Phase 1 archive/source checksums are linked from [starting_evidence.json](stage2_v1/starting_evidence.json). Every Phase 2 row identifies its exact original instance SHA-256, model and configuration. There are no tariff overlays, extra copies or changed battery/fleet parameters in the official run set. The 20–100 tariff variants are evaluated as distinct routing cases. The later structurally matched tariff pairs remain held out.

## Draft for the dataset authors

Subject — Interpretation of station visits and pricing in the Porto e-ADARP v4 release

Dear Dr. Almeida and colleagues,

We are reproducing the Zenodo v4 Porto instances. Each original has two stations with visit count one, and every vehicle appears to start at the final SOC reserve. Is the one-visit count a fleet-wide cap per physical station, or is it per vehicle? Together with no depot charging, the fleet-wide reading permits at most two vehicles to drive. Is this the intended model across all sizes? Are station visits restricted to empty vehicles? Should the embedded MMR be paid only for the station-period surplus portion, and is 22 kW an outlet/vehicle limit or a joint site cap? Could you point us to any public runnable verifier or reference schedules using these exact files?

Thank you.
