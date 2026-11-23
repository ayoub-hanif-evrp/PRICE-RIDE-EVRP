"""Read the released Casablanca workbook without silently repairing its cells."""
import csv
from collections import Counter, defaultdict
from math import isfinite
from statistics import mean, median, quantiles, pvariance

from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

from price_ride.data.acquire import TRAFFIC_DOI, TRAFFIC_NAME, TRAFFIC_SHA, digest, save_json

DAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


def positive(value):
    if type(value) in (int, float) and isfinite(value) and value > 0:
        return float(value)
    return None


def summarize(values):
    if not values:
        return {"count": 0}
    result = {"count": len(values), "min": min(values), "max": max(values),
              "mean": mean(values), "median": median(values), "variance": pvariance(values)}
    if len(values) >= 4:
        q1, _, q3 = quantiles(values, n=4, method="inclusive")
        width = q3-q1
        result["tukey_outliers"] = sum(v < q1-1.5*width or v > q3+1.5*width for v in values)
    return result


def write_csv(path, rows):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def load_observations(path):
    workbook = load_workbook(path, read_only=True, data_only=True)
    layouts, entries = {}, []
    try:
        for sheet in workbook:
            day = sheet.title.split()[-1]
            layout = {"rows": sheet.max_row, "columns": sheet.max_column}
            layouts[sheet.title] = layout
            if day not in DAYS:
                for number, row in enumerate(sheet.values, 1):
                    if any(v in ("Commune", "ZIP code", "Tables ") for v in row):
                        layout["header_row"] = number
                        layout["headers"] = {get_column_letter(i): v for i, v in enumerate(row, 1)
                                             if v is not None}
                        break
                continue
            found_header = False
            commune = postal = None
            keys = set()
            for number, row in enumerate(sheet.values, 1):
                if not found_header:
                    if row[1] == "COMMUNE" and tuple(row[12:36]) == tuple(range(24)):
                        if tuple(row[36:60]) != tuple(range(24)):
                            raise ValueError(f"{sheet.title}: TTI hour header mismatch")
                        found_header = True
                        layout["header_row"] = number
                        layout["headers"] = {"B:K": list(row[1:11]), "L": "distance (raw)",
                                             "M:AJ": "raw travel time by hour 0–23",
                                             "AK:BH": "published TTI by hour 0–23"}
                    continue
                if row[1] is not None:
                    commune, postal = str(row[1]).strip(), row[2]
                if row[3] is None and row[7] is None:
                    continue
                origin, destination = row[3], row[7]
                key = (commune, origin, destination)
                if commune is None or origin is None or destination is None or key in keys:
                    raise ValueError(f"{sheet.title}:{number}: invalid or duplicate OD {key}")
                keys.add(key)
                coordinates = [float(row[i]) if row[i] is not None else None for i in (5, 6, 9, 10)]
                for hour, (time, tti) in enumerate(zip(row[12:36], row[36:60])):
                    entries.append({"source_doi": TRAFFIC_DOI, "sheet": sheet.title, "row": number,
                                    "day": day, "hour": hour, "commune": commune, "postal_code": postal,
                                    "origin": origin, "destination": destination,
                                    "origin_lat": coordinates[0], "origin_lon": coordinates[1],
                                    "destination_lat": coordinates[2], "destination_lon": coordinates[3],
                                    "distance_raw": row[11], "travel_time_raw": time,
                                    "published_tti_raw": tti, "tti": positive(tti)})
            if not found_header:
                raise ValueError(f"{sheet.title}: no recognizable hourly header")
            layout["od_rows"] = len(keys)
        if set(row["day"] for row in entries) != set(DAYS):
            raise ValueError("workbook does not contain all seven daily layouts")
    finally:
        workbook.close()
    return layouts, entries


def audit_traffic(root):
    base = root / "datasets/casablanca"
    path = base / "raw" / TRAFFIC_NAME
    if not path.is_file() or digest(path) != TRAFFIC_SHA:
        return {"status": "BLOCKED", "reason": "official workbook missing or checksum failed"}
    sheets, entries = load_observations(path)
    grouped = defaultdict(list)
    tti_values, raw_times = [], []
    for row in entries:
        grouped[row["day"], row["hour"], row["commune"]].append(row)
        time = positive(row["travel_time_raw"])
        if time is not None:
            raw_times.append(time)
        if row["tti"] is not None:
            tti_values.append(row["tti"])
    hourly = []
    for (day, hour, commune), samples in sorted(grouped.items(),
                                                key=lambda x: (DAYS.index(x[0][0]), *x[0][1:])):
        statistics = summarize([r["tti"] for r in samples if r["tti"] is not None])
        hourly.append({"source_doi": TRAFFIC_DOI, "day": day, "hour": hour, "commune": commune,
                       "expected_count": len(samples), "valid_count": statistics["count"],
                       "mean_published_tti": statistics.get("mean"), "median_tti": statistics.get("median"),
                       "variance_tti": statistics.get("variance"), "aggregation": "arithmetic mean"})
    od_keys = {(r["commune"], r["origin"], r["destination"]) for r in entries}
    od_sites = {}
    for row in entries:
        od_sites[row["commune"], row["origin"]] = (row["origin_lon"], row["origin_lat"])
        od_sites[row["commune"], row["destination"]] = (row["destination_lon"], row["destination_lat"])
    boundary_counts = None
    boundary_path = base / "osm/boundary.geojson"
    if boundary_path.is_file():
        import json
        from shapely.geometry import Point, shape
        geometry = shape(json.loads(boundary_path.read_text(encoding="utf-8"))["features"][0]["geometry"])
        inside = {key for key, value in od_sites.items()
                  if None not in value and geometry.covers(Point(value))}
        boundary_counts = {"boundary_sha256": digest(boundary_path), "points_total": len(od_sites),
                           "points_inside": len(inside), "od_inside": sum(
                               (c, a) in inside and (c, b) in inside for c, a, b in od_keys)}
    output = base / "processed"
    output.mkdir(parents=True, exist_ok=True)
    write_csv(output / "observations.csv", entries)
    write_csv(output / "hourly_commune_tti.csv", hourly)
    result = {"status": "verified", "source": TRAFFIC_DOI, "sha256": TRAFFIC_SHA, "sheets": sheets,
              "hourly_samples": len(entries), "samples_by_day": dict(Counter(r["day"] for r in entries)),
              "samples_by_hour": dict(Counter(r["hour"] for r in entries)),
              "samples_by_commune": dict(Counter(r["commune"] for r in entries)),
              "od_keys": len(od_keys), "communes": len({k[0] for k in od_keys}),
              "hourly_commune_groups": len(hourly), "tti": summarize(tti_values),
              "missing_or_invalid_tti": len(entries)-len(tti_values),
              "missing_or_invalid_raw_travel_time": len(entries)-len(raw_times),
              "raw_travel_time": summarize(raw_times),
              "raw_travel_time_above_1440": sum(v > 1440 for v in raw_times),
              "coordinates_missing": sum(None in value for value in od_sites.values()),
              "boundary_overlap": boundary_counts,
              "travel_time_quality": "Mixed numeric scales in raw workbook. Values preserved as raw cells."
              " The official TTI values are aggregated directly, without conversion or road assignment."}
    save_json(output / "traffic_audit.json", result)
    return result
