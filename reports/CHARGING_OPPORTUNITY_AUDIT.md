# Charging opportunity audit

**GO**. All scheduled pilots found feasible fleets that required charging on the constructed routes. The energy share exceeded the pilot threshold. Independently checked station/gap probes on fixed passenger routes found lower energy bills and lower effective prices per kWh.

12 feasible fleets and 0 failed attempts. The JSON contains all runs, rejection counts, timing witnesses and source hashes.

| Requests | Tariff | Seed | Feasible | Sessions | kWh | Energy EUR | Travel min | Excess min | Objective EUR | Energy share | No-charge feasible | Runtime s |
|---:|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---|---:|
| 20 | Flat | 11 | True | 1 | 22.274 | 3.684 | 247.484 | 0.000 | 92.778 | 3.97% | False | 0.109 |
| 20 | Flat | 29 | True | 1 | 22.274 | 3.684 | 247.484 | 0.000 | 92.778 | 3.97% | False | 0.125 |
| 20 | Flat | 47 | True | 1 | 22.274 | 3.684 | 247.484 | 0.000 | 92.778 | 3.97% | False | 0.125 |
| 20 | ToU | 11 | True | 1 | 22.273 | 5.346 | 247.479 | 0.000 | 94.438 | 5.66% | False | 0.110 |
| 20 | ToU | 29 | True | 1 | 22.273 | 5.346 | 247.479 | 0.000 | 94.438 | 5.66% | False | 0.109 |
| 20 | ToU | 47 | True | 1 | 22.273 | 5.346 | 247.479 | 0.000 | 94.438 | 5.66% | False | 0.110 |
| 40 | Flat | 11 | True | 2 | 40.524 | 6.703 | 450.270 | 0.000 | 168.800 | 3.97% | False | 0.812 |
| 40 | Flat | 29 | True | 2 | 40.524 | 6.703 | 450.270 | 0.000 | 168.800 | 3.97% | False | 0.890 |
| 40 | Flat | 47 | True | 2 | 40.524 | 6.703 | 450.270 | 0.000 | 168.800 | 3.97% | False | 0.953 |
| 40 | ToU | 11 | True | 2 | 40.491 | 5.249 | 449.895 | 0.000 | 167.211 | 3.14% | False | 0.578 |
| 40 | ToU | 29 | True | 2 | 40.491 | 5.249 | 449.895 | 0.000 | 167.211 | 3.14% | False | 0.578 |
| 40 | ToU | 47 | True | 2 | 40.491 | 5.249 | 449.895 | 0.000 | 167.211 | 3.14% | False | 0.594 |

## Price and time exposure

| Tariff | Grid EUR/kWh | Station | MMR EUR/kWh | Surplus periods | Cheaper LEC periods |
|---|---|---:|---|---:|---:|
| Flat | 0.1654–0.1654 | 89 | 0.1103–0.1654 | 12 | 12 |
| Flat | 0.1654–0.1654 | 90 | 0.1103–0.1654 | 21 | 21 |
| ToU | 0.1072–0.2400 | 89 | 0.1072–0.2400 | 12 | 12 |
| ToU | 0.1072–0.2400 | 90 | 0.1072–0.2400 | 21 | 21 |

Profile station IDs shown are for the largest pilot size. Prices are taken from the two pilot sizes' original files. The data audit documents price differences between the small and large ToU files.

| Requests | Tariff | Seed | Routes charging / routes | Sites | Min / final kWh | Actual LEC discount min | Actual below-peak grid min | Fixed-route probe energy EUR | Probe LEC discount min | Optimistic price-only saving ceiling EUR |
|---:|---|---:|---|---:|---|---:|---:|---:|---:|---:|
| 20 | Flat | 11 | 1/2 (50%) | 1 | 21.21 / 40.25 | 0.00 | 0.00 | 2.716 | 65.41 | 1.228 |
| 20 | Flat | 29 | 1/2 (50%) | 1 | 21.21 / 40.25 | 0.00 | 0.00 | 2.716 | 65.41 | 1.228 |
| 20 | Flat | 47 | 1/2 (50%) | 1 | 21.21 / 40.25 | 0.00 | 0.00 | 2.716 | 65.41 | 1.228 |
| 20 | ToU | 11 | 1/2 (50%) | 1 | 21.21 / 40.25 | 0.00 | 0.00 | 2.902 | 64.51 | 2.958 |
| 20 | ToU | 29 | 1/2 (50%) | 1 | 21.21 / 40.25 | 0.00 | 0.00 | 2.902 | 64.51 | 2.958 |
| 20 | ToU | 47 | 1/2 (50%) | 1 | 21.21 / 40.25 | 0.00 | 0.00 | 2.902 | 64.51 | 2.958 |
| 40 | Flat | 11 | 2/4 (50%) | 2 | 28.79 / 40.25 | 0.00 | 0.00 | 6.161 | 39.11 | 2.234 |
| 40 | Flat | 29 | 2/4 (50%) | 2 | 28.79 / 40.25 | 0.00 | 0.00 | 6.161 | 39.11 | 2.234 |
| 40 | Flat | 47 | 2/4 (50%) | 2 | 28.79 / 40.25 | 0.00 | 0.00 | 6.161 | 39.11 | 2.234 |
| 40 | ToU | 11 | 2/4 (50%) | 2 | 28.79 / 40.25 | 0.00 | 110.43 | 4.380 | 0.00 | 0.908 |
| 40 | ToU | 29 | 2/4 (50%) | 2 | 28.79 / 40.25 | 0.00 | 110.43 | 4.380 | 0.00 | 0.908 |
| 40 | ToU | 47 | 2/4 (50%) | 2 | 28.79 / 40.25 | 0.00 | 110.43 | 4.380 | 0.00 | 0.908 |

The optimistic price-only ceiling prices every fixed purchased kWh at the day's lowest available unit rate. It ignores timing, station, outlet and finite surplus constraints. It is a theoretical ceiling and may be unattainable.

Each probe independently replays the full fleet after changing one vehicle’s charging plan. Assignments and passenger order are fixed. Probes cover the existing station and gap plus other feasible empty-vehicle station/gap placements at their earliest start and at tariff-boundary starts or ends. Same-gap retiming leaves purchased kWh fixed. Relocation can change purchased kWh and road travel. Objective behavior and witness routes are available in the JSON.

### Best checked full-objective change

| Requests | Tariff | Seed | Baseline EUR | Best probe or baseline EUR |
|---:|---|---:|---:|---:|
| 20 | Flat | 11 | 92.778 | 92.778 |
| 20 | Flat | 29 | 92.778 | 92.778 |
| 20 | Flat | 47 | 92.778 | 92.778 |
| 20 | ToU | 11 | 94.438 | 94.438 |
| 20 | ToU | 29 | 94.438 | 94.438 |
| 20 | ToU | 47 | 94.438 | 94.438 |
| 40 | Flat | 11 | 168.800 | 168.800 |
| 40 | Flat | 29 | 168.800 | 168.800 |
| 40 | Flat | 47 | 168.800 | 168.800 |
| 40 | ToU | 11 | 167.211 | 167.211 |
| 40 | ToU | 29 | 167.211 | 167.211 |
| 40 | ToU | 47 | 167.211 | 167.211 |

## Paired tariff interpretation

- 20 requests. Strict tariff-only pair **False**. Maximum matrix delta 0.248523 min. See the data audit for coordinate and time-window changes.
- 40 requests. Strict tariff-only pair **False**. Maximum matrix delta 0.511169 min. See the data audit for coordinate and time-window changes.

The verdict governs whether to continue investigating charging exposure. Published-cost comparability remains blocked by the MMR and outlet conventions in [MODEL_CONTRACT.md](MODEL_CONTRACT.md).
