# PRICE-RIDE

Stage 1 implements original data acquisition, Porto parsing, independent schedule evaluation, a constructive insertion baseline and a charging-opportunity pilot. Porto e-ADARP is the primary benchmark. The Casablanca workbook and OSM graph support a later synthetic transfer case study.

## Install and reproduce

From the project root, use Python 3.12. Tested versions are frozen in `reports/ENVIRONMENT.txt`. On Windows PowerShell:

```powershell
py -3.12 -m venv .venv
.venv/Scripts/Activate.ps1
python -m pip install -c reports/ENVIRONMENT.txt -e '.[test]'
python -m pip check
python -m price_ride.cli --help
python -m price_ride.cli data download-porto
python -m price_ride.cli data download-casablanca
python -m price_ride.cli data audit
python -m price_ride.cli model validate-porto --instance r2-20 --tariff ToU
python -m price_ride.cli baseline run --instance r2-20 --tariff ToU --seed 11
python -m price_ride.cli research charging-audit
python -m pytest -q
```

On POSIX use `python3.12 -m venv .venv` and `source .venv/bin/activate`. Porto and Casablanca acquisition are independent. The download commands resume eligible partial files and reuse verified inputs. Casablanca accepts `--traffic-only` and `--osm-only`. The OSM HTTP cache and GraphML live under `datasets/casablanca/osm/`. A new OSM extraction is a new snapshot. Compare the checksum with the original recorded graph before treating it as the same input. Downloaded and processed datasets are excluded from Git by `.gitignore`.

Use `python -m pytest -q -m 'not official'` for the standalone unit tests. The three `official` integration checks use verified local files and skip when the required files are absent. On Windows, pytest needs read and write access to its temporary directories.

To replay a saved Porto fleet and query a verified directed OSM route:

```powershell
python -m price_ride.cli model validate-porto --instance r2-20 --tariff ToU --schedule reports/pilot/ToU_r2-20_seed11.json
python -m price_ride.cli data casablanca-path 21037874 4584732034
```

The solver and evaluator are separate modules. The frozen [model contract](reports/MODEL_CONTRACT.md) defines feasibility and costing. The [data audit](reports/DATA_AUDIT.md) describes differences among official input files. The [charging audit](reports/CHARGING_OPPORTUNITY_AUDIT.md) records the pilot and its scope. The [handoff](reports/PROMPT_01_HANDOFF.md) lists the files and experimental outcome.

## Stage 2 development

The [Stage 2 protocol](reports/STAGE2_PROTOCOL.md) fixes the original development and held-out inputs, construction limits and comparisons. Run the stages in order from the project root. The campaign reuses recorded starts and results and checks the code/configuration freeze before comparison.

```powershell
$env:OPENBLAS_NUM_THREADS = '1'
$env:OMP_NUM_THREADS = '1'
python -m price_ride.optimization.campaign structural
python -m price_ride.optimization.campaign starts
python -m price_ride.optimization.campaign rescue-starts
python -m price_ride.optimization.campaign diagnostics
python -m price_ride.optimization.campaign compare
python -m price_ride.optimization.campaign replay
python -m price_ride.casablanca.transfer
```

Stage 2 result files live under `reports/stage2_v1/`. The campaign supports `--root` for a separate project-data workspace.
