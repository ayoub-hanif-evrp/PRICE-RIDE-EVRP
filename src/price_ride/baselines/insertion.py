"""Deterministic paired insertion with bounded single-stop replenishment."""
from collections import Counter
from dataclasses import replace
from itertools import combinations
from random import Random
from time import monotonic

from price_ride.domain import ChargeEvent, Route, Schedule, Stop
from price_ride.evaluation import EPS, evaluate


def schedule_order(instance, vehicle, ids, charge_minutes=0.0, charge_kwh=0.0,
                   charge_at=None, earliest_charge=None):
    """Solve fixed-route difference constraints by propagating earliest lower bounds."""
    nodes = [instance.node(i) for i in ids]
    start = [n.earliest for n in nodes]
    latest = [n.latest for n in nodes]
    latest[-1] = min(latest[-1], instance.horizon - nodes[-1].service)
    travel = [instance.travel(a, b) for a, b in zip(ids, ids[1:])]
    position = {i: idx for idx, i in enumerate(ids)}
    durations = [n.service for n in nodes]
    if charge_at is not None:
        durations[charge_at] += charge_minutes
        if earliest_charge is not None:
            start[charge_at] = max(start[charge_at], earliest_charge-nodes[charge_at].service)
    passenger_edges = []
    for r in instance.requests:
        if r.pickup in position:
            p, d = position[r.pickup], position[r.dropoff]
            passenger_edges.append((d, p, -nodes[p].service-r.max_ride))
    for _ in nodes:
        changed = False
        for i, t in enumerate(travel):
            candidate = start[i] + durations[i] + t
            if candidate > start[i+1] + EPS:
                start[i+1] = candidate
                changed = True
        for d, p, offset in passenger_edges:
            candidate = start[d] + offset
            if candidate > start[p] + EPS:
                start[p] = candidate
                changed = True
        if any(t > upper + EPS for t, upper in zip(start, latest)):
            return None
        if not changed:
            stops = tuple(Stop(node, t, charge=ChargeEvent(charge_minutes, charge_kwh)
                               if i == charge_at else None)
                          for i, (node, t) in enumerate(zip(ids, start)))
            excess = sum(start[d] - start[p] - nodes[p].service - instance.travel(ids[p], ids[d])
                         for d, p, _ in passenger_edges)
            return Route(vehicle.id, stops), sum(travel), excess
    return None


def replenishment_candidates(instance, vehicle, ids, failures, deadline):
    loads = [0]
    for node in ids:
        loads.append(loads[-1] + instance.node(node).load)
        if not 0 <= loads[-1] <= vehicle.capacity:
            failures["occupancy"] += 1
            return
    uncharged = schedule_order(instance, vehicle, ids)
    if uncharged is None:
        failures["time_window_or_ride"] += 1
        # The published travel matrix describes shortest paths. A charge detour
        # cannot repair an infeasible metric route, and this baseline skips it.
        return
    reserve = vehicle.final_ratio * vehicle.battery_kwh
    total = uncharged[1] * instance.consumption
    if vehicle.initial_kwh - total >= reserve - EPS:
        yield uncharged
        return
    prefix = 0.0
    found = False
    station_choices = [(station, node) for station in instance.stations for node in station.node_ids]
    for i, (a, b) in enumerate(zip(ids, ids[1:]), 1):
        direct = instance.travel(a, b)
        if loads[i] == 0:
            for station, node in station_choices:
                if monotonic() >= deadline:
                    return
                to_station = instance.travel(a, node)
                from_station = instance.travel(node, b)
                energy = (uncharged[1] - direct + to_station + from_station) * instance.consumption
                before = vehicle.initial_kwh - (prefix + to_station) * instance.consumption
                amount = max(0.0, reserve + energy - vehicle.initial_kwh)
                if before < -EPS or before + amount > vehicle.battery_kwh + EPS:
                    failures["single_charge_energy"] += 1
                    continue
                augmented = ids[:i] + (node,) + ids[i:]
                planned = schedule_order(instance, vehicle, augmented, amount/station.rate, amount, i)
                if planned is None:
                    failures["charging_time_window_or_ride"] += 1
                    continue
                found = True
                yield planned
        prefix += direct
    if not found:
        failures["no_single_charge_insertion"] += 1


def construct(instance, seed, seconds):
    """Return an explicitly checked complete or partial schedule with diagnostics."""
    begin = monotonic()
    deadline = begin + seconds
    rng = Random(seed)
    objective = instance.objective
    pickup_order = sorted(instance.requests, key=lambda r: (instance.node(r.pickup).earliest, rng.random()))
    vehicles = list(instance.vehicles)
    rng.shuffle(vehicles)
    orders = {v.id: (v.origin, v.destination) for v in vehicles}
    routes, scores = {}, {}
    station_by_node = {node: station for station in instance.stations for node in station.node_ids}
    failures = Counter()
    for vehicle in vehicles:
        initial = next(replenishment_candidates(instance, vehicle, orders[vehicle.id], failures, deadline), None)
        routes[vehicle.id] = initial[0] if initial else Route(vehicle.id, tuple(
            Stop(node) for node in orders[vehicle.id]))
        scores[vehicle.id] = 0.0
    uninserted = []
    budget_exhausted = False
    examined = 0
    for request in pickup_order:
        best = None
        for vehicle in vehicles:
            if monotonic() >= deadline:
                budget_exhausted = True
                break
            ids = orders[vehicle.id]
            used_nodes = {stop.node for vid, route in routes.items() if vid != vehicle.id
                          for stop in route.stops if stop.node in station_by_node}
            used_stations = Counter(station_by_node[n].id for n in used_nodes)
            # Choosing two indices in the final sequence covers every ordered pickup/dropoff insertion.
            for p, d in combinations(range(1, len(ids)+1), 2):
                if monotonic() >= deadline:
                    budget_exhausted = True
                    break
                examined += 1
                candidate = ids[:p] + (request.pickup,) + ids[p:d-1] + (request.dropoff,) + ids[d-1:]
                for route, travel, excess in replenishment_candidates(instance, vehicle, candidate,
                                                                      failures, deadline):
                    charged_nodes = [stop.node for stop in route.stops if stop.node in station_by_node]
                    if any(node in used_nodes or
                           used_stations[station_by_node[node].id] >= station_by_node[node].max_visits
                           for node in charged_nodes):
                        failures["fleet_station_visits"] += 1
                        continue
                    # Monetary service proxy uses published coefficients. Charging is
                    # replenishment-only and the proxy applies no price-aware moves.
                    score = travel*objective.travel_eur_per_min + excess*objective.excess_eur_per_min
                    key = (score - scores[vehicle.id], sum(s.charge.kwh for s in route.stops if s.charge))
                    if best is None or key < best[0]:
                        best = (key, vehicle.id, candidate, route, score)
        if best is None:
            uninserted.append(request.id)
            continue
        _, vid, orders[best[1]], routes[best[1]], scores[best[1]] = best
    schedule = Schedule(tuple(routes[vid] for vid in sorted(routes)))
    report = evaluate(instance, schedule)
    return schedule, report, {"runtime_seconds": monotonic()-begin, "budget_seconds": seconds,
                              "budget_exhausted": budget_exhausted, "seed": seed,
                              "uninserted_request_ids": uninserted,
                              "candidates_examined": examined, "rejected_constraints": dict(failures)}


def no_charge_counterfactual(instance, schedule):
    """Remove station stops and rebuild timing on the identical passenger orders."""
    station_nodes = {node for station in instance.stations for node in station.node_ids}
    vehicles = {v.id: v for v in instance.vehicles}
    routes = []
    for route in schedule.routes:
        ids = tuple(s.node for s in route.stops if s.node not in station_nodes)
        planned = schedule_order(instance, vehicles[route.vehicle], ids)
        routes.append(planned[0] if planned else replace(route, stops=tuple(Stop(id_) for id_ in ids)))
    return evaluate(instance, Schedule(tuple(routes)))
