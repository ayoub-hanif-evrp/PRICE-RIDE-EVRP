"""Input-only necessary conditions for the unchanged Porto benchmark."""
from itertools import combinations
from math import ceil, fsum
from pathlib import Path

import networkx as nx
import numpy as np

from price_ride.data.acquire import EXPECTED, digest, save_json
from price_ride.evaluation import EPS, evaluate
from price_ride.porto.parser import load_porto_instance

MODEL = "porto-v4-conservative-v2"


def closure(matrix):
    """Directed shortest-path lower bounds, ignoring all intermediate service."""
    shortest = np.array(matrix, dtype=float)
    np.fill_diagonal(shortest, 0.0)
    for k in range(len(shortest)):
        np.minimum(shortest, shortest[:, [k]] + shortest[[k], :], out=shortest)
    return shortest


def incompatible_pair(instance, first, second, shortest):
    """Every feasible one-vehicle projection has one of the six pair orders."""
    nodes = (first.pickup, first.dropoff, second.pickup, second.dropoff)
    failures = []
    for i, j in combinations(range(4), 2):
        order = [nodes[2], nodes[3]]
        order.insert(i, nodes[0])
        order.insert(j, nodes[1])
        time = 0.0
        previous = None
        for node_id in order:
            node = instance.node(node_id)
            arrival = time if previous is None else time + shortest[previous - 1, node_id - 1]
            start = max(node.earliest - EPS, arrival)
            if start > node.latest + EPS:
                failures.append({"order": order, "failed_node": node_id,
                                 "earliest_relaxed_start": float(start), "latest": node.latest})
                break
            time = start + node.service
            previous = node_id
        else:
            return None
    return failures


def compulsory_bounds(nodes, rides):
    """Return full-service workload density and simultaneous strictly on-board load."""
    best, window = 0, None
    by_completion = sorted(nodes, key=lambda n: n.latest+n.service)
    completion = np.asarray([n.latest+n.service+EPS for n in by_completion])
    services = np.asarray([n.service for n in by_completion], dtype=float)
    for lower in sorted({n.earliest-EPS for n in nodes}):
        included = np.asarray([n.earliest-EPS >= lower for n in by_completion])
        work = np.cumsum(services*included)
        valid = completion > lower
        demand = np.divide(work-EPS, completion-lower, out=np.zeros_like(work), where=valid)
        if len(demand):
            i = int(demand.argmax())
            vehicles = ceil(max(0.0, float(demand[i])))
            if vehicles > best:
                best, window = vehicles, {"start": lower, "end": float(completion[i]),
                                           "work_minutes": float(work[i]),
                                           "nodes": [n.id for n, use in zip(by_completion[:i+1],
                                                                          included[:i+1]) if use]}
    peak, at, passengers = 0, None, []
    for time in sorted({(l+r)/2 for l, r, _ in rides} |
                       {l for l, _, _ in rides}):
        active = [rid for l, r, rid in rides if l <= time < r]
        if len(active) > peak:
            peak, at, passengers = len(active), time, active
    return best, window, peak, at, passengers


def inspect(instance):
    v = instance.vehicles
    stations = instance.stations
    slots = sum(min(s.max_visits, len(s.node_ids)) for s in stations)
    initial_credit = fsum(x.initial_kwh - x.battery_kwh*x.final_ratio for x in v)
    spare = sum(x.initial_kwh-x.battery_kwh*x.final_ratio > EPS for x in v)
    matrix = np.asarray(instance.matrix)
    shortest = closure(matrix)
    positive = matrix[matrix > 0]
    strictly_active = positive.size and float(positive.min())*instance.consumption > 2*EPS
    active_upper = min(len(v), slots+spare) if strictly_active else len(v)
    max_charge = fsum(min(s.max_visits, len(s.node_ids)) *
                      min(max(x.battery_kwh for x in v)+2*EPS, (s.rate+EPS)*(instance.horizon+EPS))
                      for s in stations)
    drive_upper = (max_charge+initial_credit+2*len(v)*EPS)/instance.consumption
    mandatory = [r for r in instance.requests if min(
        shortest[x.origin-1, r.pickup-1]+shortest[r.pickup-1, r.dropoff-1]+
        shortest[r.dropoff-1, x.destination-1] for x in v) * instance.consumption > 2*EPS]
    service_nodes = [instance.node(i) for r in mandatory for i in (r.pickup, r.dropoff)]
    rides = [(instance.node(r.pickup).latest+instance.node(r.pickup).service+EPS,
              instance.node(r.dropoff).earliest-EPS, r.id) for r in mandatory]
    rides = [(l, r, i) for l, r, i in rides if l < r]
    service_lb, window, peak, at, passengers = compulsory_bounds(service_nodes, rides)
    capacity = max(x.capacity for x in v)
    ride_lb = ceil(peak/capacity)
    predecessors = [instance.node(i) for r in instance.requests for i in (r.pickup, r.dropoff)]
    predecessors += [instance.node(x.origin) for x in v]
    predecessors += [instance.node(i) for s in stations for i in s.node_ids]
    incoming = {}
    unreachable = []
    for r in instance.requests:
        for i in (r.pickup, r.dropoff):
            node = instance.node(i)
            eligible = [(instance.travel(p.id, i), p.id) for p in predecessors
                        if p.id != i and p.earliest+p.service+instance.travel(p.id, i) <= node.latest+3*EPS]
            if eligible:
                minutes, predecessor = min(eligible)
                incoming[i] = {"minutes": minutes, "predecessor": predecessor}
            else:
                unreachable.append(i)
    incoming_lb = fsum(x["minutes"] for x in incoming.values())
    passenger_lb = fsum(float(shortest[r.pickup-1, r.dropoff-1])
                       for r in instance.requests)/capacity
    travel_lb = max(incoming_lb, passenger_lb)
    certificates = []
    if unreachable:
        certificates.append({"kind": "no_incoming_arc", "nodes": unreachable})
    if travel_lb > drive_upper + EPS:
        certificates.append({"kind": "traction_bound", "lower": travel_lb, "upper": drive_upper})
    if max(service_lb, ride_lb) > active_upper:
        certificates.append({"kind": "concurrent_active_vehicles", "lower": max(service_lb, ride_lb),
                             "upper": active_upper, "workload_window": window,
                             "onboard_ids": passengers, "onboard_time": at})
    incompatible = nx.Graph()
    if active_upper <= 2 and not certificates:
        incompatible.add_nodes_from(r.id for r in mandatory)
        for a, b in combinations(mandatory, 2):
            if incompatible_pair(instance, a, b, shortest):
                incompatible.add_edge(a.id, b.id)
        if active_upper == 2 and not nx.is_bipartite(incompatible):
            odd = next(c for c in nx.cycle_basis(incompatible) if len(c) % 2)
            req = {r.id: r for r in mandatory}
            certificates.append({"kind": "odd_cycle_of_incompatible_pairs", "cycle": odd,
                                 "pair_proofs": [incompatible_pair(instance, req[a], req[b], shortest)
                                                 for a, b in zip(odd, odd[1:]+odd[:1])]})
    return {"instance": instance.name, "source": instance.source, "sha256": instance.sha256,
            "requests": len(instance.requests), "vehicles": len(v),
            "battery": [{"vehicle": x.id, "origin": x.origin, "destination": x.destination,
                         "idle_arc_minutes": instance.travel(x.origin, x.destination),
                         "initial_kwh": x.initial_kwh, "capacity_kwh": x.battery_kwh,
                         "reserve_kwh": x.battery_kwh*x.final_ratio} for x in v],
            "stations": [{"id": s.id, "copies": s.node_ids, "visits": s.max_visits} for s in stations],
            "charge_slots": slots, "active_upper": active_upper, "charge_upper_kwh": max_charge,
            "travel_upper_minutes": drive_upper, "travel_lower_minutes": travel_lb,
            "travel_lower_kwh": travel_lb*instance.consumption, "relaxed_passenger_bound": passenger_lb,
            "incoming_minima": incoming, "concurrent_service_vehicle_lower": service_lb,
            "concurrent_onboard_vehicle_lower": ride_lb, "workload_window": window,
            "mandatory_active_requests": len(mandatory), "pair_incompatibilities": incompatible.number_of_edges(),
            "strict_positive_minimum_minutes": float(positive.min()) if positive.size else None,
            "zero_arcs_off_diagonal": int(np.count_nonzero((matrix == 0) & ~np.eye(len(matrix), dtype=bool))),
            "max_shortcut_minutes": float((matrix - shortest).max()),
            "direct_request_arcs_with_shortcuts": int(sum(
                matrix[r.pickup-1, r.dropoff-1]-shortest[r.pickup-1, r.dropoff-1] > EPS
                for r in instance.requests)),
            "status": "provably infeasible" if certificates else "unresolved",
            "certificates": certificates, "witnesses": []}


def record_witness(result, instance, schedule, path, root):
    checked = evaluate(instance, schedule)
    if checked.feasible:
        if result["certificates"]:
            raise AssertionError(f"witness contradicts bound for {instance.name}")
        result["status"] = "verified feasible"
        relative = path.relative_to(root).as_posix()
        if relative not in result["witnesses"]:
            result["witnesses"].append(relative)
    return checked


def audit(root, prior_replay, added_witnesses=()):
    from price_ride.cli import load_schedule
    report_dir = root / "reports"
    frozen = root / "datasets/porto/instances"
    reference = prior_replay["data"]["instances"]
    results = []
    for relative in sorted(EXPECTED):
        instance = load_porto_instance(frozen / relative)
        if instance.sha256 != reference[relative.as_posix()]["sha256"]:
            raise ValueError(f"source hash changed: {relative}")
        result = inspect(instance)
        for path in [*sorted((report_dir/"pilot").glob(f"{relative.parts[0]}_{instance.name}_seed*.json")),
                     *[p for p in added_witnesses if p.parent.parent.name == instance.name]]:
            record_witness(result, instance, load_schedule(path, instance.sha256), path, root)
        result["held_out"] = len(instance.requests) >= 100
        results.append(result)
    values = {"model": MODEL, "cases": results}
    save_json(report_dir / "STRUCTURAL_FEASIBILITY_AUDIT.json", values)
    write_report(report_dir, values)
    return values


def write_report(directory, values):
    lines = ["# Structural feasibility on original Porto inputs", "",
             "Contract porto-v4-conservative-v2. Two physical LEC stations, each with one fleet-wide visit. "
             "All 20 files have 40.25 kWh initially and at the reserve, 57.5 kWh capacity, and zero travel "
             "from each assigned origin to its unused-route destination. Matrix zeros between different node IDs "
             "are retained. Held-out entries use inputs only.", "",
             "| Instance | N | K | Initial / reserve / cap (kWh) | Sites / visits | Active cap | Purchase upper (kWh) | Travel bounds (min) | Concurrent lower | Status |",
             "|---|---:|---:|---|---|---:|---:|---:|---:|---|"]
    for row in sorted(values["cases"], key=lambda r: (r["requests"], r["instance"])):
        battery = row["battery"][0]
        energy = " / ".join(f"{battery[k]:.2f}" for k in ("initial_kwh", "reserve_kwh", "capacity_kwh"))
        lines.append(f"| {row['instance']} | {row['requests']} | {row['vehicles']} | {energy} | "
                     f"{len(row['stations'])} / {row['charge_slots']} | {row['active_upper']} | "
                     f"{row['charge_upper_kwh']:.3f} | {row['travel_lower_minutes']:.1f}–"
                     f"{row['travel_upper_minutes']:.1f} | "
                     f"{max(row['concurrent_service_vehicle_lower'], row['concurrent_onboard_vehicle_lower'])} | "
                     f"{row['status']} |")
    lines += ["", "## Derivation", "",
              "At the reserve a vehicle consuming any positive arc larger than the replay tolerance needs a positive charge. "
              "Every such route needs one globally unique station slot. Upper purchase is the sum over slots of the lesser "
              "of maximum battery capacity and horizon times rate, with conservative tolerance. Energy balance adds the "
              "fleet's initial minus required final energy to give the traction allowance. No depot replenishment is modeled.",
              "Each compulsory passenger node needs an actual incoming arc. Its cheapest eligible predecessor is a lower "
              "bound, even when the same predecessor is counted for several nodes. Eligibility relaxes all timing except "
              "earliest predecessor completion and latest service at the destination. Directed shortest paths through all "
              "nodes, ignoring intermediate service, bound in-vehicle travel. Dividing summed direct lower bounds by "
              "maximum capacity gives another fleet travel lower bound.",
              "A mandatory active request cannot travel from any depot through both endpoints and back at zero energy, "
              "even in the shortest-path relaxation. The sum of service durations forced into a window divided by its "
              "length, rounded up, lower-bounds active vehicles. Strictly overlapping mandatory ride intervals give a "
              "capacity bound. An odd cycle in the pair incompatibility graph also needs at least three active vehicles. "
              "Each conflict tests all six precedence orders, with relaxed directed arc times and no charge, load, ride "
              "limit, or depot restrictions. The JSON records any certifying window, arc, or failed pair sequences.",
              "", "The triangle audit compares raw directed matrix entries with their shortest-path closure. "
              "Closure is for bounds only. Replay and objective use the raw arcs. Status unresolved means no "
              "certificate or saved complete witness. See [MODEL_CONTRACT_V2.md](MODEL_CONTRACT_V2.md) for the source scope."]
    (directory / "STRUCTURAL_FEASIBILITY_AUDIT.md").write_text("\n".join(lines)+"\n", encoding="utf-8")
