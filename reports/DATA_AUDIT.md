# Data audit

Parsed **20 of 20** Porto files.
Independent LEC CSV and XLSX cross-check **SOURCE DISCREPANCIES**.
For the verified release, both communities' surplus series agree with the CSV across all sizes. The 20–100 request ToU files agree with the workbook grid series, while their grid and MMR series differ from the bundled CSVs in all 96 periods. The 120–200 ToU files agree with the corresponding CSVs and disagree with the workbook grid series by up to €0.0095/kWh. Flat agrees with both sources where they provide the corresponding fields. The pilots use the tariffs embedded in each original instance.

## Official tariff variants

| Requests | Strict tariff-only pair | Latitude / longitude changes | Window start / end changes | Max matrix delta (min) |
|---:|---|---|---|---:|
| 20 | False | 1 / 1 | 15 / 15 | 0.248523 |
| 40 | False | 1 / 1 | 23 / 23 | 0.511169 |
| 60 | False | 1 / 1 | 36 / 36 | 0.511169 |
| 80 | False | 1 / 1 | 48 / 48 | 0.589126 |
| 100 | False | 1 / 1 | 62 / 62 | 0.857911 |
| 120 | True | 0 / 0 | 0 / 0 | 0.000000 |
| 140 | True | 0 / 0 | 0 / 0 | 0.000000 |
| 160 | True | 0 / 0 | 0 / 0 | 0.000000 |
| 180 | True | 0 / 0 | 0 / 0 | 0.000000 |
| 200 | True | 0 / 0 | 0 / 0 | 0.000000 |

Instance checks, source hashes, archive contents, and exact changed fields are in [DATA_AUDIT.json](DATA_AUDIT.json).

## Casablanca traffic

Workbook status **verified**.
The workbook has 13 sheets and 440 directed OD pairs across 22 communes. It provides 73,920 hourly cells, of which 73,920 carry positive finite published TTI. The commune/hour/day output has 3,696 groups.
Published TTI ranges from 0.9678 to 7.6886; pooled population variance is 0.4803. The workbook has 41,740 raw travel-time values above 1,440 despite the column label in minutes. Raw cells are retained, with units unresolved. The processed TTI is the arithmetic mean of available published indices by day/hour/commune.

| Sheet | Rows | Columns | Header row | OD rows |
|---|---:|---:|---:|---:|
| Summary | 17 | 6 | 5 | — |
| Table 0. Coordinates | 122 | 8 | 12 | — |
| Table 1. Population size in eac | 32 | 8 | 10 | — |
| Table 2. Number of Tram and Bus | 32 | 8 | 10 | — |
| Table 3. Type of roads | 32 | 15 | 10 | — |
| Table 4. Land use variables  | 32 | 10 | 10 | — |
| Table 5. Monday | 450 | 60 | 10 | 440 |
| Table 6. Tuesday | 452 | 60 | 12 | 440 |
| Table 7. Wednesday | 452 | 60 | 12 | 440 |
| Table. 8 Thursday | 452 | 60 | 12 | 440 |
| Table. 9 Friday | 452 | 60 | 12 | 440 |
| Table. 10 Saturday | 452 | 60 | 12 | 440 |
| Table. 11 Sunday | 452 | 60 | 12 | 440 |

96 / 110 sampled coordinates and 352 / 440 pairs (both endpoints) lie inside the city polygon. Endpoints support a spatial join but the workbook supplies no matched OSM paths or citywide travel matrix.

## Casablanca directed road network

Graph status **verified**.
The graph contains 38,115 nodes and 100,734 edges in 15 weak components. The largest weak and strong components have 38,081 and 37,918 nodes.
Edge lengths range from 0.584 to 3317.406 m. The three directed test paths span 6451.9, 6640.8, 12724.1 m. Full node sequences and graph provenance are in the JSON.
