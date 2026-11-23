# Shared search and PRICE-RIDE ranking

Begin with the same independently checked randomized construction for B1/B2/B3/P. Randomize pickup priority with seeded ±18-minute jitter, vehicle order and occasional choice among the top three feasible pair insertions. Prioritize missed requests in up to two restarts. Historical complete witnesses provide an explicitly logged fallback where available. Route orders are immutable tuples of nodes with assigned virtual depots. Pair moves never split a request. Equivalent unused vehicles can share an insertion target when their depot arcs, depot windows and vehicle parameters match.

## Fixed-order decoding

For each ordered route with m stops, enforce consecutive service precedence, time windows, horizon and each relation start(drop) − start(pickup) ≤ service(pickup) + max_ride. Forward propagation gives earliest feasible times. Reverse propagation gives latest feasible times. Delay pickups in reverse route order into available successor slack to reduce excess ride. This is a feasible improvement pass, with no claim of optimal accumulated ride time. Directed input arcs are used throughout. Local pair insertion uses a time-feasible direct-order proxy before station repair, a heuristic filter.

Enumerate empty-vehicle gaps and single station copies. For one charging event, minimum purchase is max(0, reserve + total travel energy − initial charge). Prefix energy checks arrival nonnegativity. Suffix energy plus reserve must fit in capacity. For two events, screen up to 24 shortest two-stop layouts when none of the uncharged or one-charge layouts is feasible. With first-arrival charge A and energy M needed between stations, the first purchase must be ≥ M − A and ≤ capacity − A. The second receives the complementary minimum purchase. Test interval endpoints and midpoint with both quantities positive. This bounded subspace can miss feasible timings. A single feasible local option may also prevent the generation of a two-charge alternative that would resolve a global conflict. No failed decode certifies infeasibility.

Positive charging uses a constant station rate at its embedded maximum. For a fixed duration, candidate starts include feasible interval endpoints, midpoint representatives, tariff boundaries and boundaries minus duration. Surplus changes on the same boundary grid. The full decoder schedules feasible interval endpoints, a middle representative and the three cheapest estimated boundary candidates. For two events the second interval is recomputed conditional on the first. Earliest feasible schedules are retained as fallback. Purchases reuse the release's periods. Price-blind decoding chooses by service cost and kWh. For every station-copy signature retain up to four unique route options so a cheaper route using different slots cannot remove a resource-compatible alternative.

The joint fleet decoder enumerates the retained Cartesian product up to the declared limit, enforces copy uniqueness and physical visits, and assesses aggregate demand once per station-period. It is exact over inspected combinations and bounded by the option pool, deadline and combination cap. Cached route options are scoped to one parsed instance and model. The key includes vehicle, immutable route order and price mode. Incumbent fallback is kept whenever decode cannot improve, and each evaluated candidate and final winner has independent replay.

## Price signal

For candidate order changes, fix the unaffected incumbent routes in a preview and compute their residual station-period surplus. Score approximate detour travel, passenger excess and purchases using the same local candidate geometry and three representative timing points. For touched-route demand q at station s in period t and residual surplus R, define the marginal preview bill as

```text
C(q,s,t) = min(q,R) × MMR(s,t) + (q−min(q,R)) × grid(t)
neutral  = Δ[0.36 × travel minutes + 0.31 × excess minutes + q × mean(grid)]
guided   = Δ[0.36 × travel minutes + 0.31 × excess minutes + sum(C(q,s,t))]
```

The neutral and guided guides each take their cheapest resource-compatible retained preview. The affected incumbent quantities and service terms are removed in the same units. Physical pricing and full monetary acceptance are identical for B3/P. The preview may miss a better charging plan and is neither an admissible bound nor an exact marginal value. Under constant grid and zero effective LEC discounts the two rankings match. If a cheap preview cannot construct an option, use a shared direct-travel estimate and retain the move as a low-priority fallback.

```text
for paired batch up to iteration and wall-time caps:
    propose common request moves around charging gaps, interleaved with random pairs
    generate reinsert, cross-route relocate and exchange proposals
    rank same proposals using the method's preview
    decode shortlisted complete orders using shared route options and fleet allocation
    independently replay each decoded fleet
    accept best improving candidate, or periodically use a bounded perturbation after stalls
    retain the best complete feasible schedule
```

The shared proposal list uses an unchanged charging-gap focus and random exploration across methods. Price-specific guidance acts on which proposals enter the limited shortlist. A guided-only accepted move is identified by absence from the neutral shortlist for that same parent and proposal batch. Trace deltas are independently replayed with both final schedules' full objective terms.

Time propagation has O(m²) worst-case cost for m route stops, and one-stop placement uses O(mS) layouts for S copy nodes. Two-stop geometry enumeration is O(m²S²) in count before its cap. Candidate insertion scans O(m²) placements before time filtering, with a cap on feasible returned candidates. Fleet combination cost is bounded by the configured pool and combination limit. Run traces record generated/pruned options, timings, cache hits, station conflicts and replay counts. The configuration and full method share one fixed development design.
