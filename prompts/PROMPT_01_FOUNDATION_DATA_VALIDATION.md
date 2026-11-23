# PROMPT 01 / 03 — Build the independent research foundation, acquire the official data, and validate feasibility

**Project:** PRICE-RIDE — Joint Electric Dial-a-Ride Routing and Electricity-Price-Aware Charging, with a Casablanca Transfer Case Study  
**Stage:** 1 of 3 — Data, model contract, evaluator, reference baseline, and early scientific go/no-go audit  
**Instruction to coding agent:** Execute this prompt in the **new project directory containing this file under `prompts/`**. Perform the work, run the tests, and leave a reproducible repository. Do not merely describe what you would do. Do not implement the proposed novel search algorithm yet; that is Prompt 02. Do not produce final paper claims yet; that is Prompt 03.

---

## 0. Read this first: the research goal and strict boundaries

We are developing an independent, respectable international-conference research project. It has **two geographically distinct evaluation components**:

1. **Primary benchmark — Porto, Portugal.** Use the original, independently published 2026 **Almeida et al. electric autonomous dial-a-ride problem (e-ADARP) with local energy communities and electricity tariffs** instances. This is the scientific benchmark for method comparison. Keep its original demand, routing, charging, tariff, and energy profiles. It is **not** a dataset of observed charging decisions or measured autonomous-taxi operations: it is a published benchmark constructed from taxi trips, OpenStreetMap and energy profiles.
2. **Secondary case study — Casablanca, Morocco.** Build the geographical and congestion-data foundations for a **clearly identified synthetic electric ride-sharing experiment grounded in real Casablanca traffic and road-network data**. There are **no verified actual Casablanca taxi request records** in the sources below. Do not describe synthetic trip requests, depot sites, charging power, or electricity prices as observed operational facts. The case study will test transfer/generalization, not replace the official Porto evaluation.

**Current working research direction:** A cost-aware algorithm that can modify passenger-to-vehicle assignments and pickup/dropoff order to enable beneficial charging decisions while preserving service and battery feasibility. The method itself will be designed and implemented in Prompt 02, once this stage establishes that the benchmark contains real opportunities for charging decisions.

### Absolute rules

- **New, standalone codebase.** Do not import, copy, adapt files from, or use as a baseline any of the researcher's previous GitHub repositories. In particular, **do not use EVMobilityBench**. Do not use Schneider EVRPTW instances or Schneider-derived alternatives.
- You may use ordinary libraries (`numpy`, `pandas`, `scipy`, `networkx`, `osmnx`, `openpyxl`, `pytest`, `pydantic`, etc.), and read the **official dataset authors' generation scripts only to understand the published data format and semantics**. Do not copy their solver code or present author-provided data-generation code as our algorithm.
- Every numeric assumption must be marked **published parameter**, **directly observed measurement**, **derived quantity**, or **explicit modeling assumption**. Never invent an unspecified energy price, customer demand stream, charging rate, or feasibility result.
- **No scientific performance invention.** A returned route is feasible only if independently checked against all applicable hard constraints. Do not silently count rejected customers as served. Do not report an objective as comparable unless its definition and units match.
- Use Python 3.11+ or 3.12 (prefer 3.12). Make all operations deterministic given a seed. Capture environment/package versions and data checksums.
- Network access may occasionally fail: implement retries, resume/skip-if-verified, meaningful failure diagnostics, and provenance reporting. Do not replace missing official data with invented toy data and call the acquisition successful.
- Work within the current project root. Keep all downloaded data in **`datasets/`**. Place reports in `reports/`, code in `src/`, tests in `tests/`. Never commit bulky raw archives or personal API credentials.

---

## 1. Create the project layout and environment

Set up a clean installable Python project with this conceptual structure (minor sensible changes are allowed; document them):

```text
<project-root>/
├── prompts/
│   └── PROMPT_01_FOUNDATION_DATA_VALIDATION.md
├── datasets/
│   ├── porto/
│   │   ├── raw/                   # immutable original Zenodo downloads
│   │   └── instances/             # extracted official ToU/ and Flat/ files
│   └── casablanca/
│       ├── raw/                   # immutable traffic workbook
│       ├── osm/                   # downloaded/frozen road graph + metadata
│       └── processed/             # reproducible derived TTI products
├── src/price_ride/
│   ├── __init__.py
│   ├── cli.py
│   ├── data/                      # download, extract, provenance, audits
│   ├── domain/                    # immutable typed model + solution objects
│   ├── porto/                     # published instance parser
│   ├── casablanca/                # raw traffic and OSM adapters
│   ├── evaluation/                # *independent* route/schedule checker
│   └── baselines/                 # minimal published-style classical baseline
├── tests/
│   ├── fixtures/                  # hand-built tiny inputs, NOT research results
│   ├── test_porto_parser.py
│   ├── test_ride_schedule.py
│   ├── test_energy_charging.py
│   ├── test_tariff_allocation.py
│   ├── test_casablanca_data.py
│   └── test_baseline_smoke.py
├── configs/
├── reports/
│   ├── DATA_PROVENANCE.md
│   ├── MODEL_CONTRACT.md
│   ├── DATA_AUDIT.md
│   ├── BASELINE_PILOT.md
│   ├── CHARGING_OPPORTUNITY_AUDIT.md
│   └── PROMPT_01_HANDOFF.md
├── scripts/
├── pyproject.toml
├── README.md
└── .gitignore
```

Create an isolated environment, install pinned compatible dependencies, and expose documented commands such as:

```bash
python -m price_ride.cli data download-porto
python -m price_ride.cli data download-casablanca
python -m price_ride.cli data audit
python -m price_ride.cli model validate-porto --instance r2-20 --tariff ToU
python -m price_ride.cli baseline run --instance r2-20 --tariff ToU --seed 11
python -m price_ride.cli research charging-audit
python -m pytest -q
```

The exact flags may differ, but they must be stable, shown in `README.md`, and executable. Support a `--help` flag. A clean clone plus documented data downloads should reproduce the repository structure.

---

## 2. Download the primary Porto benchmark from the original source

### Official source — this is the authoritative benchmark

- Dataset: **Almeida, Limmer, Soares, Bresich, Raidl & Vale (2026)**, *Dataset of Electric Autonomous Dial-a-Ride Instances with Local Energy Communities and Electricity Tariffs*.
- Zenodo **record v4**: https://zenodo.org/records/20707207
- DOI: https://doi.org/10.5281/zenodo.20707207
- Associated data paper: https://doi.org/10.1016/j.dib.2026.113063
- Open full-text data description: https://pmc.ncbi.nlm.nih.gov/articles/PMC13396958/

Download from the record **into `datasets/porto/raw/`**, keeping official names and a provenance record:

| File | Purpose | Published MD5 (verify after download) |
|---|---|---|
| `Instances.zip` | **Mandatory** original 20 benchmark instances | `4a11e54d90cd3a2bb32259739c5ce6bf` |
| `README_v2.txt` | **Mandatory** detailed block-level text format and license instructions | `418d05c225f20b9cea284a04feb42da6` |
| `results_LEC.zip` | **Mandatory** independent LEC balance/price data for cross-checks | `4d083f0fe431326dbf74c49a24de3f4f` |
| `LEC_results_midPoint.xlsx` | **Mandatory** source community profiles/metadata | `54deb508ed85dd1f37634e47a0653eb3` |
| `generate_instances.jl` | Read-only format and generation provenance | `5ba07d1150930ff2763ecf294cc9d723` |
| `group_prosumers.py` | Read-only LEC station-generation provenance | `41b510f250ca2e03a9eabd8e1cfce9e3` |

Use the Zenodo record API or the record's documented file links, rather than guessed third-party mirrors. Validate ZIP integrity, avoid ZIP path traversal, log MD5 and SHA-256, record Zenodo version, DOI, URL, retrieval UTC timestamp, license, bytes, and archive member names. Do **not** run the original Julia generation pipeline: the official generated instance files are already published, and running the pipeline could introduce version-dependent changes.

Extract to `datasets/porto/instances/` while preserving the two configurations:

- `ToU/`: expected `r2-20.txt`, `r4-40.txt`, ..., `r20-200.txt` (10 instances).
- `Flat/`: expected `rF2-20.txt`, `rF4-40.txt`, ..., `rF20-200.txt` (10 instances).

**Verify the actual extracted filenames instead of assuming the ZIP nesting.** The intended size combinations `(K vehicles, N passenger requests)` are `(2,20), (4,40), (6,60), (8,80), (10,100), (12,120), (14,140), (16,160), (18,180), (20,200)`.

A download failure must produce a meaningful status with the URL tried and the failed checksum. Do not claim that all 20 files are available if any are missing.

---

## 3. Download and freeze Casablanca's actual data sources

### 3A. Published Casablanca traffic and congestion workbook — mandatory

- **Rouky & Bousouf (2023)**, *Dataset for traffic analysis in Casablanca, Morocco*, Mendeley Data v1: https://data.mendeley.com/datasets/8hj76bpzpv/1
- DOI: https://doi.org/10.17632/8hj76bpzpv.1
- Peer-reviewed context and methods: https://doi.org/10.3390/engproc2025112056
- Description: **440 sampled origin–destination trajectories, with hourly Waze-derived travel times over a week**, plus characteristics of 22 Casablanca communes. This is **not a set of observed passenger pickup/dropoff requests**.

Download the original Excel workbook into `datasets/casablanca/raw/` using the Mendeley Data download mechanism/API and document file name, origin, checksum and CC BY 4.0 attribution. Inspect real sheet names and column layouts; do not assume a conventional CSV structure.

**If the Mendeley download endpoint is unavailable**, an author-associated public repository with the workbook is: https://github.com/abdellahbsf/traffic-congestion-data . This is a **fallback only**: explicitly mark the difference in provenance and verify the workbook really corresponds to the documented published dataset before using it. Never silently swap sources. If the fallback cannot be verified, mark Casablanca traffic data `BLOCKED` and continue with the Porto work; report the blocker.

In `src/price_ride/casablanca/traffic.py`, implement a loader and a reproducible exploratory audit that computes only quantities the real workbook supports, such as available hourly travel times, relative congestion/TTI where the denominator is defined, sample counts by day/hour/commune if available, missingness, extrema and outliers. **Do not treat 440 sampled OD pairs as 440 real taxi bookings or a complete citywide travel-time matrix.** Never assume measured Waze trajectories coincide with all routing arcs in the OSM road graph.

### 3B. Casablanca road network — mandatory for eventual city case study

Acquire a **drivable OpenStreetMap street graph for Casablanca, Morocco**, via `osmnx` / OSM data service. Freeze a checked graph under `datasets/casablanca/osm/` (e.g. `.graphml`) and save extraction metadata: place query/bounding polygon, UTC acquisition time, OSMnx and NetworkX versions, number of nodes/edges, largest connected component choices, geographic extent, directedness, and hash of the saved graph. Preserve OSM attribution and ODbL obligations.

Verify that the selected boundary actually represents **Casablanca**, not another municipality or an entire province. Build a small network-quality report showing graph connectivity, lengths, and a few valid shortest paths. Do not silently replace missing road routes with straight lines: if a fallback is necessary, mark every affected OD pair and justify it.

If Overpass/geocoding is temporarily unavailable, implement a retryable downloader and document the precise blocker. The official Porto tasks must still run. Do not use synthetic graph edges and call them OSM observations.

### 3C. Local electricity and solar data — provenance study, **not** fabricated calibration

For the Casablanca follow-up experiment, investigate accessible **official Moroccan electricity tariff** sources and **PVGIS** solar-potential data (https://joint-research-centre.ec.europa.eu/photovoltaic-geographical-information-system-pvgis_en). Make a short table in `reports/DATA_PROVENANCE.md` distinguishing verified local numbers from mere possible scenario inputs. **Do not import Porto's electricity prices as Moroccan tariffs. Do not claim that PVGIS modeled production is a measured Casablanca energy-community profile.** It is acceptable not to download these sources during Prompt 01 if their interpretation/permissions are unresolved; mark them as planned external scenarios for Prompt 03.

---

## 4. Write the exact Porto scientific model contract *before* constructing the solver

Read `README_v2.txt` and the published 2026 data paper; write `reports/MODEL_CONTRACT.md` with citations and precise units. The implementation must follow the **actual file format**, not a speculative approximation.

At minimum, verify and represent:

1. Header fields: number of vehicles `K`, requests `N`, origin/destination depots, physical charging stations, allowed station visits, and planning horizon.
2. Pickup–dropoff pairing, original IDs, virtual per-vehicle depot nodes, virtual copies of charging stations if present, original WGS84 coordinates, travel-time matrix indexing, time windows, and service durations.
3. Request constraints: pickup before dropoff, both on the **same vehicle**, every request served **exactly once**, passenger occupancy from node loads `+1`/`-1`, passenger capacity, maximum on-board ride duration, time-window feasibility and waiting.
4. Vehicle energy constraints: initial energy, capacity, energy use per minute of **actual travel**, energy after each arc, battery limits, and **minimum final SOC** for each vehicle. Do not consume traction energy while stationary unless expressly specified.
5. Charging: location, station accessibility and visit rules, charge rate, nonnegative duration and amount, maximum battery capacity, 96 **15-minute** energy/tariff intervals over the 1,440-minute day, and station/LEC-specific price and renewable overproduction data.
6. Cost components: time-travel cost, passenger **excess ride time** and electricity purchase cost. Recover the published unit conversions and weights from the files/paper and store them as named configuration values. **Do not combine raw minutes and euros with an undocumented coefficient.** Keep raw metrics separately regardless of scalar objective choice.

Published article reference checks (these are **sanity checks**, not substitutes for parsing the files): nominal battery 57.5 kWh; maximum occupancy 4 passengers; travel consumption 0.09 kWh/min; minimum destination SOC 70%; maximum passenger ride time 60 min; 30-min request windows; two LEC stations with nominal charging power 22 kW each (0.367 kWh/min); 96 price periods; 1,440-min horizon. If the published file differs, **use the actual file value and explain the discrepancy**.

**Critical tariff detail:** The article specifies that electricity purchased at a local-energy-community (LEC) price is **limited by the community's finite 15-minute surplus**, with the remainder bought at the grid tariff. When multiple vehicles charge in the same period, any shared LEC surplus **must not be counted twice**. Check the README/paper for the exact intended allocation and simultaneous-charging convention. If an ambiguity remains, implement an explicitly named and documented assumption, test conservation, and report that it may limit comparability. Also distinguish the station's charging-power bound from any independently supported simultaneous charging-outlet capacity; do not invent a queue or outlet count.

The source paper describes the overall objective as a weighted combination of travel cost, passenger excess ride time, and charging cost. Define one **frozen, explicit benchmark objective contract** and raw-component metrics; do not select weights after seeing which method performs best. If a necessary convention remains ambiguous, mark the objective comparison as blocked until it is resolved. No phantom "published optimum" claims: the 2026 article introduces a benchmark and does not publish optimal routing solutions for all 20 instances.

---

## 5. Implement the standalone parser and typed domain model

Write original Python code (not copied from prior repos):

- Typed, preferably immutable structures for `Instance`, `Request`, `Vehicle`, `Node`, `ChargingStation`, `TimeSeries`, `Route`, `Stop`, `ChargeEvent`, `Schedule`, `EvaluationReport`.
- `load_porto_instance(path)` loads **all actual blocks** using the author README, including long matrix rows and charging-station copies. Never assume that a station copy is another physical charger. Report malformed data with line numbers where possible.
- Validate matrix dimensions and finite/nonnegative entries; node/pair IDs; coordinate ranges; matching pickup/dropoff loads; valid vehicle start/end locations; 96-element tariff/surplus arrays; tariff nonnegativity; battery/charge-rate units; constraints within the time horizon.
- Compare `ToU` and `Flat` instances of the same size: check which fields are identical and which truly differ, rather than assuming only prices change. Write a paired-variant audit.
- Preserve a raw-input checksum and source identifier inside each loaded instance.
- Provide `data audit` output as machine-readable JSON and human-readable Markdown, covering the **entire 20-file** official set.

Do not use unverified Euclidean distances in place of the provided Porto **road-network travel-time matrix**.

---

## 6. Implement a strict, independent e-ADARP route-and-fleet evaluator

The evaluator is the scientific ground truth for all later algorithm comparisons. Build it as its own module with **no calls to the baseline or future optimizer**. It must accept a complete explicit solution (ordered stops and, where relevant, charge quantities/durations and departure/wait decisions), and return:

- `feasible: bool`, full violation list with vehicle/request/stop indices and magnitudes, and explanation;
- per-stop arrival, service-start, departure, load, SOC and passenger state;
- each request's pickup/dropoff timestamps and actual/excess ride time;
- travel time, waiting/service time, charging time, charged energy (kWh), charging cost (€), grid versus LEC-supplied energy (kWh), travel/user costs (€), and full objective under the frozen contract;
- per-vehicle initial/final SOC, minimum en-route SOC, station visits, time-window slack, and horizon compliance.

Required scientific checks:

- Every request served exactly once; no duplicates/missing requests. Pickup precedes dropoff **on the same vehicle**. Loads stay in `[0, capacity]`, with no dropoff before pickup and empty passenger load at a completed depot return.
- Time-window service starts and waiting; start/finish horizon; service time; **maximum passenger on-board ride time** (do not confuse with departure-to-departure time). Define excess ride time consistently with the data paper.
- Energy is consumed on every traveled leg according to travel-time * published rate, not Euclidean distance or payload-dependent energy. No negative SOC; charging is physically bounded and obeys station rules. Minimum **70% final SOC**, or the instance-specific published ratio, is enforced.
- Charge energy spanning several 15-minute tariff intervals is allocated across those intervals by actual charging rate and duration. Test boundaries at minute 15, 30, ..., 1,440. Surplus kWh is conserved **across all vehicles**, never counted twice.
- Charging and passenger timing must remain causally consistent. No teleporting between nodes or instant charging; energy from a later time interval cannot be bought earlier.
- Add tolerances with explicit engineering rationale, not broad lax allowances that hide violations.

Write **hand-calculated micro-tests**, including: a valid pickup/dropoff; a reversed pair; split-vehicle pair; time-window failure; ride-time failure; capacity overflow; battery shortfall; final-SOC shortfall; valid partial recharge; charging across a price boundary; simultaneous chargers sharing limited renewable surplus; unreachable/invalid arc; and depot return.

If the source's station-outlet or renewable allocation semantics remain ambiguous, document the exact ambiguity, implement the least speculative named contract, and **do not call results official-comparable until it is resolved**.

---

## 7. Implement a minimal *independent* classical baseline to expose feasibility and charging headroom

This is **not the proposed paper algorithm**. Build a simple original constructive comparator:

1. Sort request pairs by earliest pickup time (deterministic seed-based tiebreaking).
2. Insert each pickup and its dropoff together into feasible locations of an existing vehicle route; test multiple insertion positions while preserving precedence. Select by the **frozen published-style cost** or a clearly stated lexicographic feasibility-first proxy where exact scalar cost is unavailable.
3. Permit waiting, passenger-safe scheduling and depot return.
4. First attempt **no charging**; independently evaluate. If charging is needed, add a **bounded, simple** charging insertion mechanism: consider physical station visits, arrival SOC and feasible charge durations; never invent charging capacity or price. It is acceptable to use a small CP-SAT/MILP subroutine for charging decisions on a fixed short route, but this is a reference baseline, not the research contribution.
5. Record failure reasons when a complete feasible solution cannot be found; never silently drop requests and report a valid result.
6. Provide a reproducible time limit, search seed, and output route/schedule JSON verified by the independent evaluator.

Run the baseline with at least **three predefined seeds** on the **20-request and 40-request** Porto instances, both tariffs, and optionally one 60-request instance if feasible. Select reasonable fixed time limits and record them. A simple comparator is sufficient now; **do not spend most of Prompt 01 building an advanced ALNS or the proposed price-aware operator**.

Also supply a separate **diagnostic no-charging feasibility check** for constructed routes. Its purpose is to reveal whether charging is actually required; it must not transform invalid routes into valid ones by skipping battery rules.

---

## 8. The crucial research go/no-go audit: is price-aware charging actually relevant?

Before developing a novel routing method, compute `reports/CHARGING_OPPORTUNITY_AUDIT.md` and a corresponding JSON/CSV file. Use **only actual measured outputs and rigorously labeled bounds**. This is mandatory because the published battery and request configurations might allow many routes to operate without intermediate charging.

For each tested Porto size/tariff/seed, report:

1. Number of fully feasible solutions found versus failed attempts; which constraints caused failure; runtime.
2. Baseline total travel minutes, excess ride minutes, total monetary cost and **total energy cost**; never report an infeasible solution as comparable cost.
3. Number and fraction of routes requiring an intermediate paid charging session, charged kWh, number of stations used, and min/final battery levels.
4. A **no-charge counterfactual** on the same constructed routes: whether the routes remain feasible (including minimum final SOC); distinguish "no charging needed" from "charging not found."
5. Range and temporal variation of grid and community-adjusted prices, number of 15-minute periods with positive available renewable surplus, and actual temporal overlap between possible/used charge intervals and cheaper periods.
6. Charging's share of the complete objective. If relevant, report a **theoretical price-only bound explicitly labeled as non-attainable** (e.g. best possible tariff paid for fixed kWh without accounting for scheduling feasibility); never present this bound as an achieved saving.
7. Whether `ToU` versus `Flat` provides genuinely paired comparisons under identical pickup/dropoff and travel data.

**Hard go/no-go gate:** If the small/medium *official* Porto instances consistently need no intermediate charging, or electricity cost is negligible relative to passenger/travel cost, explicitly mark the current **price-aware charging contribution as `NO-GO / NEEDS REFRAME`** in the handoff. Do **not** artificially reduce battery capacity, inflate energy consumption, increase request counts, or retune published windows just to force a positive result and still call those original benchmark results. A clearly labeled *additional sensitivity scenario* may be considered in Prompt 02 only after an honest original-benchmark audit.

If constructing a complete feasible baseline remains difficult, report `INCONCLUSIVE` rather than mistaking baseline failure for physical infeasibility. A limited reference solution from a small exact model may help validate the simulator but does not prove general feasibility.

---

## 9. Prepare the Casablanca transfer dataset without overstating its evidence

Use the official Mendeley congestion workbook and frozen OSM road graph to prepare an **audited data layer** for a later city case study. Scope for Prompt 01:

- Read and preserve original hourly/day-of-week congestion information and commune identifiers where actually available; document missing coordinates or spatial matching information.
- Create a normalized processed table of defensible **hourly congestion indicators** (e.g., relative travel-time multipliers/TTI), with data source, aggregation rule and valid hour/day keys. Measure coverage and variance. Do not extrapolate measured Waze observations to all road segments as if observed; a network-wide multiplier model must be explicitly labeled **estimated/simulated**, with sensitivity scenarios.
- Preserve the directed OSM topology and real edge lengths. Implement a prototype shortest-path query with verified connected nodes and an explicit treatment of one-way roads.
- Establish reusable interfaces for an eventual Casablanca **synthetic passenger-request generator**, tariff scenario module and station-site assumptions, but **do not present generated requests or arbitrary Moroccan tariffs as real observations**.
- The eventual experiment should use the **same algorithm and feasibility evaluator** as Porto, adapted through documented instance inputs. No tuning the algorithm separately on the final Casablanca scenarios to manufacture generalization claims.

For Prompt 01 you may create a tiny **clearly labeled synthetic** Casablanca smoke fixture only to exercise the interface. The full case-study demand/charging scenario design belongs in Prompt 03, after the Porto method is validated.

---

## 10. Acceptance tests — do not report success without running these

At completion, actually execute and record these checks (or precisely document a network-only blocker):

- [ ] New independent Python project installs cleanly; no imports or copied code from prior research repositories.
- [ ] Official Porto source downloads under `datasets/porto/raw/`, with MD5/SHA-256 verification and original archive metadata.
- [ ] Exactly **20** original Porto instances are extracted and pass structural validation: 10 ToU + 10 Flat, sizes 20 through 200 requests.
- [ ] Every original instance has finite dimensional travel-time matrices, correct request pairing, valid vehicle/station references, and 96-element LEC/tariff vectors.
- [ ] Actual Casablanca congestion workbook downloaded under `datasets/casablanca/raw/` or a **clearly documented** source-download blocker/fallback; sheet/column audit generated.
- [ ] Casablanca OSM driving graph downloaded and frozen under `datasets/casablanca/osm/` or an explicit external-data blocker; connectivity and metadata assessed.
- [ ] Independent simulator passes hand-calculated feasibility, charging, tariff-period and surplus-conservation tests.
- [ ] At least one 20-request Porto instance is run through the constructive baseline (record feasible **or** specific failure; never fake feasibility). Baseline attempts for 20/40-size both tariff scenarios are logged.
- [ ] The central **charging-opportunity audit** exists, including an honest `GO`, `NO-GO` or `INCONCLUSIVE` conclusion supported by observed runs.
- [ ] `python -m pytest -q` exits successfully for tests that do not require network; network-dependent tests are isolated, marked and reproducible.
- [ ] Source and model contracts, actual outputs, commands, package versions and limitation statements are saved in `reports/`.

### Report formats and minimum files

Produce the files above plus:

- `reports/DATA_AUDIT.json` containing source IDs, hashes, instance checks and validation failures;
- `reports/CHARGING_OPPORTUNITY_AUDIT.json` containing reproducible per-instance/seed metrics and explicit feasibility status;
- `configs/experiment_stage1.yaml` fixing the chosen seeds, small instance identifiers and budgets **before results are inspected**;
- `reports/PROMPT_01_HANDOFF.md` stating actual completed work, commands executed, test counts, problems, dataset/price-related scientific risks, and exactly what Prompt 02 can safely assume.

Save diagnostic plots only if supported by real data; mark any illustrative simulation unambiguously. Do not create invented improvement-percentage charts.

---

## 11. Stop conditions and decisions for the agent

- **Dataset is unavailable:** Stop *that source's* acquisition path, retain working code, document the exact blocker and verified alternatives. Do not mislabel a fabricated file as downloaded. Continue independent work that is not blocked.
- **Published format is ambiguous:** Read README, paper and data-generation script for semantics; implement only grounded behavior, document any remaining assumption. Do not assert official comparability where the objective/constraints differ.
- **Benchmark has no actual charging opportunity:** Report it clearly as `NO-GO` for the current price-aware hypothesis. The project is not a failure; this prevents an invalid paper direction. Propose a **brief** scientifically compatible pivot to congestion-/passenger-service-aware joint routing (to decide in Prompt 02), but do not silently pivot algorithms.
- **Baseline finds no feasible solution:** Diagnose the parser/evaluator and construction limits, distinguish `INCONCLUSIVE` from proven infeasible, and do not manufacture favorable metrics.
- **Time/resource limits:** Prioritize (a) exact Porto parser and evaluator, (b) verified official downloads, (c) smallest-instance baseline and charging audit, (d) Casablanca data preparation. Complete as much as possible and state precisely what remains.

---

## 12. What to return at the end

After coding and running the work, return a concise engineering/research handoff with:

1. **Real filesystem tree** and all files implemented, including `datasets/` contents and origin verification.
2. **Executed commands** with outcomes, number of passing tests, and exact data counts. Report exceptions honestly.
3. A short table for the 20- and 40-request cases: feasibility, number of charge sessions, charged kWh, energy cost, travel/excess ride metrics, and runtime. Use `N/A` for metrics on invalid solutions.
4. **Explicit go/no-go/inconclusive research verdict** on whether *price-aware charging* has enough exposure in the published Porto benchmark.
5. Short, concrete description of what Prompt 02 should implement **only after this evidence**.

**Do not:** present the coding agent's generated results as peer-reviewed findings, state the algorithm already improves a baseline, start the novel algorithm prematurely, copy from previous repos, change the official Porto dataset to force charging, or turn synthetic Casablanca OD pairs into supposed observed taxi journeys.

---

## 13. Three-prompt roadmap (for context only)

- **Prompt 01 (this file):** Independent repository, official Porto and Casablanca data acquisition, faithful model and evaluator, independent simple baseline, key opportunity audit and go/no-go.
- **Prompt 02 (later, provided separately):** If the opportunity audit passes, independently implement and ablate the novel **price-/LEC-opportunity-aware passenger assignment and joint charging search**; fair matched-budget baselines and development-only tuning. If the audit fails, adapt the research direction transparently instead of forcing the tariff idea.
- **Prompt 03 (later, provided separately):** Locked Porto study, statistically controlled experiments, documented Casablanca synthetic transfer scenarios grounded in observed congestion/OSM data, sensitivity tests, plots, comparison with published literature, reproducibility package, and conference-paper draft.

**Begin now. Prioritize correct data and model fidelity over clever heuristics.**
