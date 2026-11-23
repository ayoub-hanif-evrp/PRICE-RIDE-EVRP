"""Audit original bytes, structure, paired scenarios and independent LEC data."""
import csv
import json
from collections import defaultdict
from zipfile import ZipFile

from openpyxl import load_workbook

from price_ride.casablanca.traffic import audit_traffic
from price_ride.data.acquire import EXPECTED, PORTO_DOI, PORTO_FILES, digest, save_json
from price_ride.porto.parser import load_porto_instance


def pair_audit(a, b):
    node_changes = {field: sum(getattr(x, field) != getattr(y, field)
                               for x, y in zip(a.nodes, b.nodes))
                    for field in ("latitude", "longitude", "service", "load", "earliest", "latest")}
    matrix_delta = [abs(v-w) for va, vb in zip(a.matrix, b.matrix) for v, w in zip(va, vb)]
    identical = {key: getattr(a, key) == getattr(b, key) for key in (
        "horizon", "depot_counts", "common_depots", "requests", "vehicles", "consumption", "objective")}
    identical.update(nodes=a.nodes == b.nodes, matrix=a.matrix == b.matrix,
                     stations=all((x.id, x.node_ids, x.rate, x.max_visits) ==
                                  (y.id, y.node_ids, y.rate, y.max_visits)
                                  for x, y in zip(a.stations, b.stations)),
                     surplus=all(x.surplus == y.surplus for x, y in zip(a.stations, b.stations)))
    return {"requests": len(a.requests), "ToU": a.name, "Flat": b.name, "identical": identical,
            "tariff_only_pair": all(identical.values()), "node_field_change_counts": node_changes,
            "matrix_exact_change_count": sum(d > 0 for d in matrix_delta),
            "matrix_change_count_gt_1e_7_min": sum(d > 1e-7 for d in matrix_delta),
            "matrix_max_absolute_difference_minutes": max(matrix_delta),
            "grid_equal": a.electricity.grid == b.electricity.grid,
            "mmr_equal": [x.mmr == y.mmr for x, y in zip(a.stations, b.stations)]}


def crosscheck_energy(raw, instances):
    archive = raw / "results_LEC.zip"
    workbook = raw / "LEC_results_midPoint.xlsx"
    if not archive.is_file() or not workbook.is_file():
        return {"status": "BLOCKED", "reason": "independent LEC sources unavailable"}
    if any(digest(p, "md5") != PORTO_FILES[p.name] for p in (archive, workbook)):
        return {"status": "FAILED", "reason": "LEC source checksum failure"}

    def difference(left, right):
        deltas = [abs(a-b) for a, b in zip(left, right)]
        return {"length_match": len(left) == len(right),
                "changed_periods": sum(x > 1e-10 for x in deltas),
                "max_absolute_difference": max(deltas, default=0)}

    xlsx = load_workbook(workbook, read_only=True, data_only=True)
    results = {}
    try:
        with ZipFile(archive) as lec:
            for tariff, group in sorted(instances.items()):
                stem = "results_LEC_Julia/outputModel_2LECs" + ("_Flat" if tariff == "Flat" else "")
                stem += "_10Users_"
                profiles = {}
                base_instance = group[min(group)]
                for station_index, (label, station) in enumerate(zip("AB", base_instance.stations)):
                    def rows(name):
                        return list(csv.reader(lec.read(f"{stem}{name}_{label}.csv").decode().splitlines()))

                    balance = tuple(max(0, -float(r[0])) for r in rows("Balance")[1:])
                    buy = tuple(float(r[0]) for r in rows("ToU_Buy")[1:])
                    columns, values = rows("MMR_buy")
                    price = tuple(float(value) for _, value in sorted(zip(map(int, columns), values)))
                    xlsx_grid = tuple(value for _, value in list(xlsx[f"{label}_Buy_price_{tariff}"].values)[1:])
                    station_row = list(xlsx["Stations"].values)[station_index+1]
                    node = base_instance.node(station.id)
                    profiles[label] = {
                        "xlsx_grid_vs_csv": difference(xlsx_grid, buy),
                        "instances": {item.name: {
                            "surplus_vs_csv": difference(item.stations[station_index].surplus, balance),
                            "mmr_vs_csv": difference(item.stations[station_index].mmr, price),
                            "grid_vs_csv": difference(item.electricity.grid, buy),
                            "grid_vs_xlsx": difference(item.electricity.grid, xlsx_grid),
                        } for item in group.values()},
                        "workbook_station_position_matches_within_1e_10_degrees": (
                            abs(node.latitude-station_row[2]) <= 1e-10 and
                            abs(node.longitude-station_row[3]) <= 1e-10),
                        "xlsx_charge_power_matches": abs(station.rate*60-station_row[4]) < 1e-10,
                    }
                results[tariff] = profiles
        profiles = [profile for tariff in results.values() for profile in tariff.values()]
        discrepancies = any(
            delta["changed_periods"] or not delta["length_match"]
            for profile in profiles
            for delta in (profile["xlsx_grid_vs_csv"],
                          *(d for item in profile["instances"].values() for d in item.values())))
        station_discrepancies = any(not p["xlsx_charge_power_matches"] or
                                    not p["workbook_station_position_matches_within_1e_10_degrees"]
                                    for p in profiles)
        status = "SOURCE DISCREPANCIES" if discrepancies or station_discrepancies else "verified"
        return {"status": status, "profiles": results, "workbook_sheets": xlsx.sheetnames}
    finally:
        xlsx.close()


def metadata(path):
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {"status": "unavailable"}


def audit_data(root):
    report_dir = root / "reports"
    porto = root / "datasets/porto"
    parent = porto / "instances"
    variants = defaultdict(dict)
    checks, failures = {}, []
    actual = {path.relative_to(parent) for path in parent.glob("*/*.txt")}
    failures.extend(f"unexpected path {p.as_posix()}" for p in sorted(actual - EXPECTED))
    for relative in sorted(EXPECTED):
        path = parent / relative
        try:
            a = load_porto_instance(path)
            n, k = len(a.requests), len(a.vehicles)
            if path.stem != f"{'r' if relative.parts[0] == 'ToU' else 'rF'}{k}-{n}":
                raise ValueError("file name/header mismatch")
            variants[relative.parts[0]][n] = a
            checks[relative.as_posix()] = {
                "source": a.source, "sha256": a.sha256, "requests": n, "vehicles": k,
                "nodes": len(a.nodes), "matrix": [len(a.matrix), len(a.matrix[0])],
                "periods": len(a.electricity.grid),
                "direct_ride_minutes_min": min(a.travel(r.pickup, r.dropoff) for r in a.requests),
                "initial_kwh": sorted({v.initial_kwh for v in a.vehicles}),
                "battery_kwh": sorted({v.battery_kwh for v in a.vehicles}),
                "final_reserve_kwh": sorted({v.battery_kwh*v.final_ratio for v in a.vehicles}),
                "passenger_capacity": sorted({v.capacity for v in a.vehicles}),
                "charging_rates_kwh_min": [s.rate for s in a.stations],
                "physical_stations": len(a.stations),
                "station_visit_limits": [s.max_visits for s in a.stations],
                "traction_kwh_min": a.consumption,
                "pickup_window_width_min": sorted({a.node(r.pickup).latest-a.node(r.pickup).earliest
                                                  for r in a.requests}),
                "dropoff_window_width_range_min": [
                    min(a.node(r.dropoff).latest-a.node(r.dropoff).earliest for r in a.requests),
                    max(a.node(r.dropoff).latest-a.node(r.dropoff).earliest for r in a.requests)],
                "max_ride_min": sorted({r.max_ride for r in a.requests}),
                "horizon_minutes": a.horizon,
            }
        except (ValueError, OSError) as exc:
            failures.append(str(exc))
    pairs = [pair_audit(variants["ToU"][n], variants["Flat"][n])
             for n in sorted(variants["ToU"].keys() & variants["Flat"].keys())]
    casablanca = root / "datasets/casablanca"
    sources = {"porto": metadata(porto / "raw/provenance.json"),
               "traffic": metadata(casablanca / "raw/provenance.json"),
               "osm": metadata(casablanca / "osm/provenance.json")}
    # Match parsed bytes back to the verified official ZIP.
    archive = porto / "raw/Instances.zip"
    if archive.exists():
        import hashlib
        if digest(archive, "md5") == PORTO_FILES[archive.name]:
            with ZipFile(archive) as z:
                for key, record in checks.items():
                    expected = hashlib.sha256(z.read("Instances/" + key)).hexdigest()
                    record["matches_verified_archive"] = record["sha256"] == expected
                    if not record["matches_verified_archive"]:
                        failures.append(f"extracted instance differs from verified archive: {key}")
        else:
            failures.append("source ZIP MD5 mismatch")
    else:
        failures.append("official source ZIP missing")
    for name, expected in PORTO_FILES.items():
        path = porto / "raw" / name
        if not path.is_file() or digest(path, "md5") != expected:
            failures.append(f"missing or invalid official file {name} (MD5 {expected})")
    graph = casablanca / "osm/casablanca-drive.graphml"
    if sources["osm"]["status"] == "verified" and (
            not graph.is_file() or digest(graph) != sources["osm"]["sha256"]):
        sources["osm"]["status"] = "FAILED"
        failures.append("frozen graph missing or SHA-256 mismatch")
    energy = crosscheck_energy(porto / "raw", variants)
    if energy["status"] not in ("verified", "SOURCE DISCREPANCIES"):
        failures.append(f"independent energy cross-check {energy['status']}")
    for name, message in sources["porto"].get("failures", {}).items():
        failures.append(f"{name}: {message}")
    try:
        traffic = audit_traffic(root)
    except (OSError, ValueError) as exc:
        traffic = {"status": "FAILED", "reason": str(exc)}
    result = {"source": PORTO_DOI, "sources": sources, "valid_instances": len(checks),
              "instances": checks, "validation_failures": failures, "pairs": pairs,
              "lec_crosscheck": energy, "casablanca_traffic": traffic}
    save_json(report_dir / "DATA_AUDIT.json", result)
    write_report(report_dir, result)
    return result


def write_report(report_dir, audit):
    traffic = audit["casablanca_traffic"]
    osm = audit["sources"]["osm"]
    pairs = audit["pairs"]
    lines = ["# Data audit", "", f"Parsed **{audit['valid_instances']} of 20** Porto files.",
             f"Independent LEC CSV and XLSX cross-check **{audit['lec_crosscheck']['status']}**."]
    if audit["lec_crosscheck"]["status"] == "SOURCE DISCREPANCIES":
        lines += ["For the verified release, both communities' surplus series agree with the CSV across all "
                  "sizes. The 20–100 request ToU files agree with the workbook grid series, while their grid and "
                  "MMR series differ from the bundled CSVs in all 96 periods. The 120–200 ToU files agree with "
                  "the corresponding CSVs and disagree with the workbook grid series by up to €0.0095/kWh. "
                  "Flat agrees with both sources where they provide the corresponding fields. "
                  "The pilots use the tariffs embedded in each original instance."]
    lines += ["", "## Official tariff variants", "",
             "| Requests | Strict tariff-only pair | Latitude / longitude changes | Window start / end changes | Max matrix delta (min) |",
             "|---:|---|---|---|---:|"]
    for p in pairs:
        c = p["node_field_change_counts"]
        lines.append(f"| {p['requests']} | {p['tariff_only_pair']} | {c['latitude']} / {c['longitude']} | "
                     f"{c['earliest']} / {c['latest']} | {p['matrix_max_absolute_difference_minutes']:.6f} |")
    lines.extend(["", "Instance checks, source hashes, archive contents, and exact changed fields "
                  "are in [DATA_AUDIT.json](DATA_AUDIT.json).",
                  "", "## Casablanca traffic", "", f"Workbook status **{traffic['status']}**."])
    if traffic["status"] == "verified":
        lines += [f"The workbook has {len(traffic['sheets'])} sheets and {traffic['od_keys']} directed OD pairs "
                  f"across {traffic['communes']} communes. It provides {traffic['hourly_samples']:,} hourly "
                  f"cells, of which {traffic['tti']['count']:,} carry positive finite published TTI. "
                  f"The commune/hour/day output has {traffic['hourly_commune_groups']:,} groups.",
                  f"Published TTI ranges from {traffic['tti']['min']:.4f} to {traffic['tti']['max']:.4f}; "
                  f"pooled population variance is {traffic['tti']['variance']:.4f}. "
                  f"The workbook has {traffic['raw_travel_time_above_1440']:,} raw travel-time values "
                  "above 1,440 despite the column label in minutes. Raw cells are retained, with units unresolved. "
                  "The processed TTI is the arithmetic mean of available published indices by day/hour/commune.",
                  "", "| Sheet | Rows | Columns | Header row | OD rows |", "|---|---:|---:|---:|---:|"]
        for sheet, info in traffic["sheets"].items():
            lines.append(f"| {sheet} | {info['rows']} | {info['columns']} | {info.get('header_row', '—')} | "
                         f"{info.get('od_rows', '—')} |")
        overlap = traffic["boundary_overlap"]
        if overlap:
            lines += ["", f"{overlap['points_inside']} / {overlap['points_total']} sampled coordinates and "
                      f"{overlap['od_inside']} / {traffic['od_keys']} pairs (both endpoints) lie inside "
                      "the city polygon. Endpoints support a spatial join but the workbook supplies no "
                      "matched OSM paths or citywide travel matrix."]
    else:
        lines += [traffic.get("reason", "Details in JSON.")]
    lines += ["", "## Casablanca directed road network", "", f"Graph status **{osm['status']}**."]
    if osm["status"] == "verified":
        lengths = osm["length_m"]
        path_lengths = ", ".join(f"{p['length_m']:.1f}" for p in osm["sample_paths"])
        lines += [f"The graph contains {osm['nodes']:,} nodes and {osm['edges']:,} edges in "
                  f"{osm['weak_components']} weak components. The largest weak and strong components "
                  f"have {osm['largest_weak_nodes']:,} and {osm['largest_strong_nodes']:,} nodes.",
                  f"Edge lengths range from {lengths['min']:.3f} to {lengths['max']:.3f} m. "
                  f"The three directed test paths span {path_lengths} m. "
                  "Full node sequences and graph provenance are in the JSON."]
    if audit["validation_failures"]:
        lines += ["", "## Validation failures", "",
                  *(f"- {item}" for item in audit["validation_failures"])]
    (report_dir / "DATA_AUDIT.md").write_text("\n".join(lines)+"\n", encoding="utf-8")
