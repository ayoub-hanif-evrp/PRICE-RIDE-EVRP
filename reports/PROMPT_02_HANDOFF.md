# Prompt 02 handoff

**NO-GO for the current PRICE-RIDE superiority claim and the planned Prompt 03 performance campaign.** PRICE-RIDE improved one of 36 common-feasible development pairs against the matched full-objective B3 control and tied 35. Median improvement was **0.000%**, below the frozen **0.5%** threshold. Mean gain was **0.0183%**. All eight configuration medians and all 14 common-feasible validation-seed comparisons were zero. There was no P-specific feasibility loss. [Development results](STAGE2_DEVELOPMENT_RESULTS.md) · [Paired data and raw-row index](STAGE2_DEVELOPMENT_RESULTS.json)

## What the runs established

The diagnostic evaluated 566 candidate fleets from fixed common incumbents. Of 564 feasible candidates, 355 lowered the full objective and 286 lowered charging cost. Charging-only decoding improved the original fixed passenger order's total cost for 14 of 36 complete diagnostic starts, with a maximum improvement of €3.411. The guided shortlist order changed in 43 of 108 batches, including eight first-choice changes. Both shortlists returned the same best replayed objective in all 108 batches. [Joint opportunity audit](JOINT_OPPORTUNITY_AUDIT.md)

In end-to-end development, B3 and P both evaluated 2,160 moves, with equal move counts in all 36 completed pairs. On the P trajectories, price information changed the shortlisted order in 151 of 432 batches and changed the first choice in 39. Two accepted moves appeared only in P's shortlist. One was an objective-improving move, and the other was a bounded perturbation. The isolated improvement was `r6-60` ToU, seed 47. At 60 move evaluations each, P reduced the charging bill by €1.735 and added €0.353 in travel cost with unchanged user cost. The resulting €1.383 total gain was **0.658%**. This confirms the mechanism in one run and leaves the configuration median at zero. [P trace](stage2_v1/r6-60/runs/47_P.json) · [Matched B3 trace](stage2_v1/r6-60/runs/47_B3.json)

| Method | Development fleets feasible / planned | Exact move trials | Median accounted runtime (s) |
|---|---:|---:|---:|
| B0 — historical constructor | 40 / 40 | — | 1.767 |
| B1 — routing-focused control | 36 / 40 | 2,160 | 9.689 |
| B2 — routing plus fixed-order charging | 36 / 40 | 2,145 | 9.451 |
| B3 — full-objective joint control | 36 / 40 | 2,160 | 9.764 |
| P — price-guided joint search | 36 / 40 | 2,160 | 10.139 |

Runtime includes attributed shared construction and incomplete-start attempts. B2 reserves 25% of the remaining post-construction budget for fixed-order charging. B0 has its own construction. B3 beat B1 in 13 of 36 common-feasible development pairs and lost in eight. Its median gain was 0.000% and its mean gain was 0.136%. The results files preserve conditional cost means, per-instance feasibility, signed component deltas, charged kWh, effective price, grid/LEC split, active vehicles, SOC and checks. These are paired runs on the same original files and within-case seeds.

## Official benchmark and validation

| Original size | Cases with a verified witness | Shared construction |
|---|---:|---|
| 20 | 2 / 2 | 7 / 7 seeds per tariff |
| 40 | 2 / 2 | 7 / 7 seeds per tariff |
| 60 | 2 / 2 | 7 / 7 seeds per tariff |
| 80 | 2 / 2 | 4 / 7 seeds per tariff after the timed rerun; historical B0 served all five development seeds per tariff |
| 100–200 | 0 / 12, unresolved | Held out. Input-only bounds for every original. |

Every original starts at its 40.25 kWh reserve and has two fleet-wide visit slots under the declared interpretation. At most two vehicles can drive a positive-travel route. Assigned unused-depot arcs are zero, and the shortest nonzero raw arc is 0.009337 minutes, large enough for energy use to exceed replay tolerance. The all-file relaxed purchase cap is approximately 115 kWh, giving about 1,277.8 possible traction minutes. Per-case travel lower bounds range from 86.0 to 243.8 minutes. No lower bound certifies infeasibility. The largest directed matrix shortcut was 1.96e-14 minutes, within tolerance. Signed excess is retained for nonmetric inputs outside the tolerance. [Structural report](STRUCTURAL_FEASIBILITY_AUDIT.md) · [Machine-readable derivations and witnesses](STRUCTURAL_FEASIBILITY_AUDIT.json)

The 10 s initial construction timed out on all 14 size-80 case-seeds. A 20 s rerun was frozen before paired comparisons and produced eight witnesses. Both attempts count against each method's existing 60 s limit. The other six seeds remain unresolved starts, represented by 20 method rows. The historical control's feasible 80-request schedules show this is a limitation of the shared constructor. No failed heuristic run was treated as infeasibility. Official files and tariff profiles match their original hashes. The 20–100 ToU and Flat routing inputs differ, so the comparisons stay within each file. The fleet visit rule, possible MMR blending and aggregate outlet power remain open for author clarification. [Protocol](STAGE2_PROTOCOL.md) · [Model contract and unsent author draft](MODEL_CONTRACT_V2.md)

## Executed checks and artifacts

| Check | Observed outcome |
|---|---|
| Starting Git commit | `5f52020578224f06106512cb0938cbb80cb54451`. All 23 hashed Phase 1 artifacts match, and all 12 Phase 1 schedules replay with identical objective values. |
| Frozen implementation commit | `c07e92afdf636e1a0bf23668a9a080c9baf41d8c`. The subsequent evidence commit contains this handoff and the results. |
| `python -m pytest -q` and `python -m pip check` | 48 tests passed on the Phase 1 baseline, then 60 passed on Phase 2. The adversarial boolean vehicle-ID test exposed a replay bug and passes after the exact-integer check. No broken dependencies. |
| `python -m price_ride.optimization.campaign structural`, `starts`, `rescue-starts` | Audited all 20 hashes. Retained 56 initial starts generated with the same Python functions and verified that the CLI resumes them. Ran and retained all 14 bounded reruns through the CLI. Fixed a NumPy JSON serialization issue and an integer-service test fixture dtype issue in the structural audit. |
| `python -m price_ride.optimization.campaign diagnostics` | 40 rows, including four unresolved starts. Completed diagnostics took 94.3 s in aggregate. |
| `python -m price_ride.optimization.campaign compare` | 232 rows, 212 feasible schedules, 20 unresolved-start rows and zero method runtime overruns. Search/comparison consumed about 1,765 s excluding repeated shared-start accounting. |
| `python -m price_ride.optimization.campaign replay` | 262 schedules verified, 40 rows with no saved schedule, zero replay failures. Also replayed the saved 80 ToU seed-47 candidate through the public `model validate-porto` CLI. |
| `python -m price_ride.casablanca.transfer` | Two explicitly synthetic requests passed directed graph and independent service validation. Verified 3,696 TTI groups and checked 12 sample endpoint snaps. [Protocol and fixture](CASABLANCA_TRANSFER_PROTOCOL.md) |

The machine was Windows 11, Intel family 6 model 183, and Python 3.12.10. Campaign optimization ran sequentially with one BLAS/OpenMP thread. Package versions, exact input identities and experimental code checksums are in [starting evidence](stage2_v1/starting_evidence.json) and [comparison freeze](stage2_v1/comparison_freeze.json). All 70 start rows, 40 diagnostic rows, 232 method rows and checked schedules are preserved in [stage2_v1](stage2_v1/). Read [the method](PRICE_RIDE_METHOD.md) and [literature positioning](LITERATURE_POSITIONING.md) for the shared option-pool limits and why price-aware dial-a-ride and targeted LNS operators already have precedent.

## Gates and next decision

| Gate | Status | Evidence |
|---|---|---|
| Phase 1 preservation and original-data integrity | PASS | [Preservation checks](stage2_v1/phase1_preservation.json) |
| Original development cohort of at least four case configurations | PASS | [Eight verified original cases](STRUCTURAL_FEASIBILITY_AUDIT.md) |
| Evaluator, shared charging and independent replay | PASS | [Replay verification](stage2_v1/replay.json) |
| Genuine price-induced move changes | PASS | [Diagnostic](JOINT_OPPORTUNITY_AUDIT.md) and [one favorable trace](stage2_v1/r6-60/runs/47_P.json) |
| 0.5% median gain and positive median in at least half of distinct cases | FAIL | [Matched comparison](STAGE2_DEVELOPMENT_RESULTS.md) |
| No systematic P-specific feasibility loss | PASS | [Paired outcome rows](STAGE2_DEVELOPMENT_RESULTS.json) |
| Published station scope, outlet and MMR interpretation | UNRESOLVED | [Contract and clarification draft](MODEL_CONTRACT_V2.md) |
| Larger untouched cohort | UNRESOLVED | [100–200 structural bounds](STRUCTURAL_FEASIBILITY_AUDIT.md) |
| Casablanca transfer preparation | PASS | [Synthetic fixture and source protocol](CASABLANCA_TRANSFER_PROTOCOL.md) |

Keep the held-out Porto files locked. If the project continues, obtain clarification on the model and freeze a revised hypothesis before a new development experiment. The isolated gain provides a traceable example for studying when LEC exposure changes a passenger move. It does not justify running the planned superiority campaign or using the Casablanca transfer to compensate for weak Porto evidence.
