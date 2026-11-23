# Prompt 01 handoff

## Scientific verdict

**GO for Prompt 02 method development.** All 12 planned runs in the official 20- and 40-request cases produced complete, independently verified fleets. Every vehicle starts at the 40.25 kWh final reserve. Removing intermediate charging and rescheduling the same passenger routes caused destination-reserve violations in every pilot fleet. Charging contributed 3.14–5.66% of the verified pilot objective, above the frozen 1% negligibility threshold.

With passenger assignments and order fixed, feasible charging relocations reduced charging cost by €0.54–€2.44 per fleet and reduced the effective price per kWh. The best-energy witnesses added enough travel that each had a higher total objective. Retiming alone at the original stop and gap produced no measured saving. These findings establish tariff exposure and motivate testing whether passenger assignment and stop-order changes can lower detour costs. The pilot estimates no improvement from a joint method.

| Requests | Tariff | Feasible / attempted | Sessions | kWh | Charge EUR | Travel min | Excess ride min | Objective EUR | Runtime per seed (s) |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 20 | ToU | 3 / 3 | 1 | 22.273 | 5.346 | 247.479 | 0.000 | 94.438 | 0.109–0.110 |
| 20 | Flat | 3 / 3 | 1 | 22.274 | 3.684 | 247.484 | 0.000 | 92.778 | 0.109–0.125 |
| 40 | ToU | 3 / 3 | 2 | 40.491 | 5.249 | 449.895 | 0.000 | 167.211 | 0.578–0.594 |
| 40 | Flat | 3 / 3 | 2 | 40.524 | 6.703 | 450.270 | 0.000 | 168.800 | 0.812–0.953 |

Results within each case had identical reported costs and times across seeds 11, 29 and 47, aside from wall-clock runtimes. The pilot used two published LEC sites and the conservative empty-vehicle and fleet-wide station visit rules. Exactly half the available vehicles operated routes with positive travel and charging in these pilots. The pilot cost contract, probes, ceilings, route checks and actual profiles are indexed in [CHARGING_OPPORTUNITY_AUDIT.md](CHARGING_OPPORTUNITY_AUDIT.md) and [CHARGING_OPPORTUNITY_AUDIT.json](CHARGING_OPPORTUNITY_AUDIT.json).

## Executed checks

Commands use the isolated Python 3.12.10 environment. The environment freeze is [ENVIRONMENT.txt](ENVIRONMENT.txt).

| Command or check | Result |
|---|---|
| `py -3.12 -m venv .venv` and `python -m pip install -e '.[test]'` | Environment created and project installed. Windows sandbox retries allowed network and temporary-directory access. |
| `python -m pip check` | No broken requirements. |
| `python -m price_ride.cli --help` | CLI usage returned successfully. |
| `python -m price_ride.cli data download-porto` | Six published MD5 matches and verified SHA-256 recorded. Both ZIPs pass CRC. Twenty originals extracted. |
| `python -m price_ride.cli data download-casablanca` | Primary Mendeley workbook checksum and frozen OSM graph verified. A temporary Mendeley API connection reset cleared on retry. |
| `python -m price_ride.cli data audit` | Twenty structurally valid Porto originals, ten per tariff. Casablanca workbook and graph verified. Secondary Porto tariff discrepancies recorded. |
| `python -m price_ride.cli model validate-porto --instance r2-20 --tariff ToU` | Valid structure, 46 nodes, 20 requests and two vehicles. |
| `python -m price_ride.cli model validate-porto --instance r2-20 --tariff ToU --schedule reports/pilot/ToU_r2-20_seed11.json` | Independently replayed a saved feasible fleet tied to the source checksum. |
| `python -m price_ride.cli baseline run --instance r2-20 --tariff ToU --seed 11` | Complete feasible schedule saved. |
| `python -m price_ride.cli research charging-audit` | 12 feasible, zero failed. All 12 saved schedules were subsequently replayed. |
| `python -m price_ride.cli data casablanca-path 21037874 4584732034` | Directed road route, 6,451.947 m. |
| `python -m pytest -q` | 48 passed, including three local official-data integration checks. The sandboxed first attempt hit Windows pytest temp permissions. It also exposed a shortest-path tie difference before vs. after GraphML reload. The final graph quality uses the saved graph and passes round-trip verification. |
| `python -m pytest -q -m 'not official'` | 45 unit tests passed, three integration checks deselected. |

No official-data source remained blocked. The 20-file structural check, per-file checksums and comparative audits are in [DATA_AUDIT.md](DATA_AUDIT.md) and [DATA_AUDIT.json](DATA_AUDIT.json). The workbook has 13 sheets, 440 directed sampled OD pairs, 22 communes and 73,920 published TTI values. Of 110 sampled coordinates, 96 are inside the frozen Casablanca city boundary. Both endpoints are inside for 352 sampled pairs. The graph contains 38,115 nodes and 100,734 directed edges. Its largest strongly connected component has 37,918 nodes.

## Limitations for Prompt 02

- The supplied Flat and ToU variants at 20–100 requests differ in routing data, including small changes in travel times. Use each original file unchanged. Restrict tariff-only claims to audited 120–200 pairs or use a clearly labeled controlled tariff overlay on a fixed routing instance.
- Small and large official ToU files also differ in embedded electricity profiles. The 20–100 files' grid prices match the XLSX. The 120–200 files' grid and MMR prices match the bundled LEC CSVs. Use the embedded profiles per instance. The published MMR description and aggregate charger power convention still need clarification for comparisons against external objective values. The exact assumptions and sources are in [MODEL_CONTRACT.md](MODEL_CONTRACT.md).
- The workbook's hourly travel cells have mixed numerical scales. Preserve raw cells as released and use the published TTI for descriptive aggregation. A Casablanca transfer experiment needs its own explicit synthetic demand, site, congestion and electricity scenarios. See [DATA_PROVENANCE.md](DATA_PROVENANCE.md).
- The simple comparator uses one replenishment stop per active route and earliest-window pair insertion without backtracking. Pilot coverage is limited to 20/40 requests and examines one vehicle's charging change at a time. Prompt 02 can build price- and LEC-aware reassignment and ordering moves, then compare them under matched budgets against routing-only and charging-only controls. Keep delivery, ride-time, station visits, final SOC and fleet tariff allocation independently verified.

## Workspace inventory

```text
PRICE-RIDE/
├── .gitignore
├── README.md
├── pyproject.toml
├── configs/experiment_stage1.yaml
├── prompts/PROMPT_01_FOUNDATION_DATA_VALIDATION.md
├── src/price_ride/
│   ├── __init__.py
│   ├── cli.py
│   ├── domain.py
│   ├── evaluation.py
│   ├── research.py
│   ├── baselines/{__init__.py,insertion.py}
│   ├── casablanca/{__init__.py,network.py,scenarios.py,traffic.py}
│   ├── data/{__init__.py,acquire.py,audit.py}
│   └── porto/{__init__.py,parser.py}
├── tests/
│   ├── conftest.py
│   ├── test_baseline_smoke.py
│   ├── test_casablanca_data.py
│   ├── test_energy_charging.py
│   ├── test_porto_parser.py
│   ├── test_ride_schedule.py
│   └── test_tariff_allocation.py
├── reports/
│   ├── BASELINE_PILOT.md
│   ├── CHARGING_OPPORTUNITY_AUDIT.{md,json}
│   ├── DATA_AUDIT.{md,json}
│   ├── DATA_PROVENANCE.md
│   ├── ENVIRONMENT.txt
│   ├── MODEL_CONTRACT.md
│   ├── PROMPT_01_HANDOFF.md
│   └── pilot/ (12 schedule and replay JSON files)
└── datasets/
    ├── porto/
    │   ├── raw/
    │   │   ├── Instances.zip
    │   │   ├── LEC_results_midPoint.xlsx
    │   │   ├── README_v2.txt
    │   │   ├── generate_instances.jl
    │   │   ├── group_prosumers.py
    │   │   ├── provenance.json
    │   │   └── results_LEC.zip
    │   └── instances/
    │       ├── Flat/ (rF2-20.txt through rF20-200.txt, 10 originals)
    │       └── ToU/ (r2-20.txt through r20-200.txt, 10 originals)
    └── casablanca/
        ├── raw/
        │   ├── Dataset for traffic analysis in Casablanca, Morocco.xlsx
        │   └── provenance.json
        ├── osm/
        │   ├── boundary.geojson
        │   ├── casablanca-drive.graphml
        │   ├── provenance.json
        │   └── http-cache/
        └── processed/
            ├── hourly_commune_tti.csv
            ├── observations.csv
            └── traffic_audit.json
```

The CLI supplies the reproducibility commands. The synthetic micro-fixtures are defined in `tests/conftest.py` and the test modules. `.venv/`, runtime caches and installed package metadata are omitted above.
