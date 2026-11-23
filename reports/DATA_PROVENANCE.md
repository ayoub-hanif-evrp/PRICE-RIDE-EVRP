# Data provenance

## Porto benchmark

Almeida, Limmer, Soares, Bresich, Raidl and Vale (2026), *Dataset of Electric Autonomous Dial-a-Ride Instances with Local Energy Communities and Electricity Tariffs*, Zenodo v4, DOI 10.5281/zenodo.20707207, CC BY 4.0. The six original files are under `datasets/porto/raw/`. All published MD5 values match. [Zenodo release](https://zenodo.org/records/20707207) · [Data paper](https://doi.org/10.1016/j.dib.2026.113063)

| File | Published MD5 |
|---|---|
| Instances.zip | `4a11e54d90cd3a2bb32259739c5ce6bf` |
| README_v2.txt | `418d05c225f20b9cea284a04feb42da6` |
| results_LEC.zip | `4d083f0fe431326dbf74c49a24de3f4f` |
| LEC_results_midPoint.xlsx | `54deb508ed85dd1f37634e47a0653eb3` |
| generate_instances.jl | `5ba07d1150930ff2763ecf294cc9d723` |
| group_prosumers.py | `41b510f250ca2e03a9eabd8e1cfce9e3` |

[DATA_AUDIT.json](DATA_AUDIT.json) records publisher URLs, UTC retrieval times, MD5, SHA-256, bytes and archive members. The 20 extracted instance hashes were compared to the archive members. Generation scripts and README informed the parser and LEC cross-check. The simulation uses the publisher's instance files as released. Porto taxi origin and destination coordinates and OSM routing underlie the benchmark. Time windows and community charging sites are modeled. Third-party source terms in the archive README apply to any independent redistribution of those underlying sources.

## Casablanca traffic and roads

- Rouky and Bousouf (2023), *Dataset for traffic analysis in Casablanca, Morocco*, Mendeley Data v1, DOI 10.17632/8hj76bpzpv.1, CC BY 4.0. The published Mendeley file API supplied the download URL and SHA-256 `4778abffbe3d7791afa58069fc8a98b6e89995174d4c64401d9367221c42d17d`. The 1,720,067-byte workbook matches. The workbook contains Waze-derived travel estimates for sampled OD trajectories, published derived TTI, and built-environment data. [Dataset](https://data.mendeley.com/datasets/8hj76bpzpv/1) · [Methods paper](https://www.mdpi.com/2673-4591/112/1/56)
- © OpenStreetMap contributors, ODbL 1.0. OSMnx froze a directed driving graph for the Casablanca city administrative relation 4072985 using Nominatim and the primary Overpass endpoint. All weak components are retained, and sample paths are drawn from the largest strongly connected component. `boundary.geojson` and `casablanca-drive.graphml` are under `datasets/casablanca/osm/`. Graph SHA-256 `60af359a9dcec1371b4984a97f6d2c5536d6542ae7f420f6c778523d299fa73f`. Preserve attribution and follow ODbL obligations when sharing graph data. [OSM relation](https://www.openstreetmap.org/relation/4072985) · [OSM copyright and license](https://www.openstreetmap.org/copyright)

The traffic workbook records endpoints. Its published indices are derived at the trajectory level, with no verified mapping of Waze paths to OSM edges. The commune/hour TTI tables aggregate observed source rows. Passenger requests, depots and charging stations for the eventual experiment will be explicit scenario assumptions. A road-wide multiplier derived from the sampling would be a simulated model.

## Moroccan tariff and solar sources

| Source | Verified published information | Potential Prompt 03 scenario input |
|---|---|---|
| ONEE general medium-voltage tariff | The published national utility schedule quotes peak, full and off-peak energy charges of 1.4157, 1.0101 and 0.7398 MAD/kWh including 18% VAT, plus a fixed 512.62 MAD/kVA/year. [ONEE medium-voltage tariff](https://www.one.org.ma/FR/pages/interne.asp?esp=1&id1=14&id2=114&t2=1) | Confirm the applicable Casablanca distributor, contract class, study date, voltage, tax treatment, time convention and capacity charge before using any schedule. No station tariff was calibrated. |
| European Commission JRC PVGIS | The public tool estimates location-specific photovoltaic production from irradiation and modeled system assumptions. [JRC PVGIS](https://joint-research-centre.ec.europa.eu/photovoltaic-geographical-information-system-pvgis_en) | A modeled PV scenario may use specified site, PV sizing, losses and weather period. Deriving available surplus also requires a separately justified load/storage scenario. No local production or LEC surplus was measured or downloaded. |

Original sources are immutable in `raw/`. OSM provenance and processed products have separate locations. Published Porto operating parameters are kept in the instance data. Data summaries and physical quantities calculated from those inputs are derived. Pilot budgets, thresholds, allocation rules and scheduling conventions are documented modeling or experiment decisions.
