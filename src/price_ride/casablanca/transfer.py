"""Check frozen inputs and build a graph-native synthetic reachability fixture."""
import argparse
import csv
import json
from dataclasses import asdict
from pathlib import Path
from random import Random

import networkx as nx
import numpy as np
import osmnx as ox
from shapely.geometry import Point, shape

from price_ride.casablanca.network import shortest_path
from price_ride.data.acquire import TRAFFIC_NAME, TRAFFIC_SHA, digest, save_json
from price_ride.domain import ChargingStation, Instance, Node, Objective, Request, Route, Schedule, Stop, TimeSeries, Vehicle
from price_ride.evaluation import evaluate

FIXTURE_SEED = 20261123
SPEED_KMH = 30.0
TRACTION_KWH_KM = 0.18


def transfer_check(root):
    data = root/"datasets/casablanca"
    graph_file = data/"osm/casablanca-drive.graphml"
    boundary_file = data/"osm/boundary.geojson"
    workbook = data/"raw"/TRAFFIC_NAME
    stage1 = json.loads((root/"reports/DATA_AUDIT.json").read_text(encoding="utf-8"))
    frozen = stage1["sources"]["osm"]
    if (digest(graph_file) != frozen["sha256"] or digest(boundary_file) != frozen["boundary_sha256"]
            or digest(workbook) != TRAFFIC_SHA):
        raise ValueError("transfer source checksum mismatch")
    graph = ox.load_graphml(graph_file)
    if not graph.is_directed() or len(graph) != frozen["nodes"] or graph.number_of_edges() != frozen["edges"]:
        raise ValueError("directed graph inventory differs from source")
    scc = sorted(max(nx.strongly_connected_components(graph), key=lambda c: (len(c), -min(c))))
    if len(scc) != frozen["largest_strong_nodes"]:
        raise ValueError("SCC differs from audited graph")
    zone = shape(json.loads(boundary_file.read_text(encoding="utf-8"))["features"][0]["geometry"])
    lats = np.array([graph.nodes[n]["y"] for n in scc])
    lons = np.array([graph.nodes[n]["x"] for n in scc])

    with (data/"processed/hourly_commune_tti.csv").open(encoding="utf-8", newline="") as tti:
        rows = list(csv.DictReader(tti))
        keys = {(r["day"], int(r["hour"]), r["commune"]) for r in rows if int(r["valid_count"]) > 0}
    if len(keys) != stage1["casablanca_traffic"]["hourly_commune_groups"]:
        raise ValueError("TTI coverage differs from audited workbook")
    with (data/"processed/observations.csv").open(encoding="utf-8", newline="") as times:
        sample_points = {(float(r["origin_lat"]), float(r["origin_lon"]))
                         for r in csv.DictReader(times) if r["origin_lat"] and r["origin_lon"]}
    snaps = []
    for lat, lon in sorted(p for p in sample_points if zone.covers(Point(p[1],p[0])))[:12]:
        distance = ox.distance.great_circle(lat, lon, lats, lons)
        k = int(distance.argmin())
        snaps.append({"source_endpoint": [lat, lon], "nearest_scc_node": scc[k],
                      "straight_line_snap_m": float(distance[k])})

    anchor = frozen["sample_paths"][0]["origin"]
    center = graph.nodes[anchor]
    distance = ox.distance.great_circle(center["y"], center["x"], lats, lons)
    eligible = [scc[i] for i in np.flatnonzero((distance < 2500) & (distance > 200))]
    # Graph-native synthetic endpoints. Workbook OD points only inform the separate snap audit.
    points = Random(FIXTURE_SEED).sample(eligible, 6)
    route_nodes = (points[0], points[1], points[2], points[3], anchor, anchor, points[4], points[5])
    matrix_m = tuple(tuple(0 if a == b else shortest_path(graph, a, b)["length_m"] for b in route_nodes)
                     for a in route_nodes)
    matrix = tuple(tuple(m*60/(1000*SPEED_KMH) for m in row) for row in matrix_m)
    route_order = (5, 1, 3, 2, 4, 6)
    window_begin = {}
    clock = 420.0
    for prev, current in zip(route_order, route_order[1:]):
        clock += matrix[prev-1][current-1] + (3 if prev <= 4 else 0)
        window_begin[current] = clock
    nodes = tuple(Node(i, graph.nodes[n]["y"], graph.nodes[n]["x"], 3 if i <= 4 else 0,
                       1 if i <= 2 else -1 if i <= 4 else 0,
                       window_begin[i] if i <= 4 else 0,
                       window_begin[i]+30 if i <= 4 else 1440)
                  for i, n in enumerate(route_nodes, 1))
    zero = (0.0,)*96
    sites = tuple(ChargingStation(i, (i,), .3, 1, zero, zero) for i in (7, 8))
    scenario = Instance("casablanca-synthetic-fixture", "frozen Casablanca OSM and explicit test assumptions",
                        frozen["sha256"], 1440, (1, 1), (5, 6), nodes,
                        (Request(1, 1, 3, 30), Request(2, 2, 4, 30)),
                        (Vehicle(1, 5, 6, 2, 30, 42, .5),),
                        sites, TimeSeries(15, zero), TRACTION_KWH_KM*SPEED_KMH/60,
                        Objective((0, 0), 0, 0), matrix)
    schedule = Schedule((Route(1, tuple(Stop(i, 420 if i == 5 else None) for i in route_order)),))
    checked = evaluate(scenario, schedule)
    output = {
        "scope": "synthetic reachability and evaluator fixture; no cost or performance experiment",
        "seed": FIXTURE_SEED, "graph_sha256": frozen["sha256"], "traffic_sha256": TRAFFIC_SHA,
        "largest_scc": len(scc), "tti_groups": len(keys), "snap_checks": snaps,
        "assumed_speed_kmh": SPEED_KMH, "assumed_traction_kwh_per_km": TRACTION_KWH_KM,
        "scenario_osm_nodes": route_nodes, "directed_metres": matrix_m,
        "service_feasible": checked.feasible, "served": len(checked.rides),
        "travel_minutes": checked.metrics.travel_minutes, "final_soc_kwh": checked.vehicles[0].final_kwh,
        "feasible_checked_schedule": asdict(schedule),
        "violations": [asdict(v) for v in checked.violations],
    }
    save_json(root/"reports/stage2_v1/casablanca_fixture.json", output)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    result = transfer_check(parser.parse_args().root)
    print("synthetic fixture", result["service_feasible"], result["served"],
          "sampled SCC snaps", len(result["snap_checks"]))
    return int(not result["service_feasible"])


if __name__ == "__main__":
    raise SystemExit(main())
