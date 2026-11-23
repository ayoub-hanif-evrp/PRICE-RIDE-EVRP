"""Matched routing backbone with optional tariff-aware move ranking."""
from collections import Counter, defaultdict
from dataclasses import dataclass
from hashlib import sha256
from itertools import product
from random import Random
from time import perf_counter

from price_ride.evaluation import EPS, evaluate
from price_ride.optimization.charging import Decoder
from price_ride.optimization.orders import Move, passenger_orders, proposals
from price_ride.optimization.timing import Timing


@dataclass(frozen=True)
class Preview:
    move: Move
    service: float
    neutral: float
    guided: float
    uses_fallback: bool


def orders_id(orders):
    return sha256(repr(orders).encode("ascii")).hexdigest()[:16]


def score_delta(old, new):
    a, b = old.metrics, new.metrics
    return {key: getattr(b, key)-getattr(a, key)
            for key in ("travel_eur", "user_eur", "energy_eur", "objective_eur",
                        "travel_minutes", "excess_ride_minutes", "charged_kwh")}


def metric(report, priced):
    m = report.metrics
    return m.objective_eur if priced else m.travel_eur+m.user_eur


def preview_moves(instance, decoder, current, moves, deadline):
    begin = perf_counter()
    schedule, checked = current
    costs = instance.objective
    charge_by_vehicle = defaultdict(list)
    for a in checked.allocations:
        charge_by_vehicle[a.vehicle].append((a.station, a.period, a.grid_kwh+a.lec_kwh))
    service_by_vehicle = {}
    for route in schedule.routes:
        travel = sum(instance.travel(a.node, b.node) for a, b in zip(route.stops, route.stops[1:]))
        excess = sum(r.excess_minutes for r in checked.rides if r.vehicle == route.vehicle)
        service_by_vehicle[route.vehicle] = travel*costs.travel_eur_per_min + excess*costs.excess_eur_per_min
    variable = max(decoder.grid) != min(decoder.grid) or any(
        q > EPS and abs(m-g) > EPS for s in instance.stations
        for q, m, g in zip(s.surplus, s.mmr, decoder.grid))

    ranked = []
    for move in moves:
        if perf_counter() >= deadline:
            break
        touched = {i+1 for i in move.touched}
        fixed_nodes = {s.node for r in schedule.routes if r.vehicle not in touched
                       for s in r.stops if s.node in decoder.by_node}
        fixed_sites = Counter(decoder.by_node[v].id for v in fixed_nodes)
        old_demand, residual = [], {}
        for vehicle, demand in charge_by_vehicle.items():
            if vehicle in touched:
                old_demand.extend(demand)
            else:
                for s, p, q in demand:
                    residual[s, p] = max(0.0, residual.get((s, p), decoder.by_site[s].surplus[p])-q)
        old_service = sum(service_by_vehicle[i] for i in touched)
        old_flat = sum(x[2] for x in old_demand)*decoder.reference
        old_bill = decoder.bill(old_demand, residual)
        route_options = []
        for i in move.touched:
            opts = decoder.options(i+1, move.orders[i], True, deadline, preview=True, residual=residual)
            groups = defaultdict(list)
            for o in opts:
                if not fixed_nodes.intersection(o.slots):
                    groups[o.slots].append(o)
            per_slot = []
            for options in groups.values():
                for cost in (lambda x: x.service_cost+x.kwh*decoder.reference,
                             lambda x: x.service_cost+decoder.bill(x.demand, residual)):
                    selected = min(options, key=cost)
                    if selected not in per_slot:
                        per_slot.append(selected)
            route_options.append(per_slot)

        feasible = []
        for choices in product(*route_options):
            slots = [s for o in choices for s in o.slots]
            if len(set(slots)) != len(slots):
                continue
            counts = fixed_sites + Counter(decoder.by_node[s].id for s in slots)
            if any(n > decoder.by_site[s].max_visits for s, n in counts.items()):
                continue
            value = sum(o.service_cost for o in choices)-old_service
            nominal = sum(o.kwh for o in choices)*decoder.reference-old_flat
            actual = decoder.bill((d for o in choices for d in o.demand), residual)-old_bill
            feasible.append((value, value+nominal, value+actual))
        if feasible:
            scores = tuple(min(p[i] for p in feasible) for i in range(3))
            service, plain, aware = scores
            ranked.append(Preview(move, service, plain, aware if variable else plain, False))
            continue
        # Both methods can still explore a move whose cheap one-charge preview fails.
        geometries = [Timing(instance, move.orders[i], instance.vehicles[i]) for i in move.touched]
        estimate = sum(t.travel*costs.travel_eur_per_min for t in geometries)-old_service
        value = estimate+sum(t.travel for t in geometries)*instance.consumption*decoder.reference-old_flat
        ranked.append(Preview(move, estimate, value, value, True))
    decoder.counts["preview_candidates"] += len(ranked)
    decoder.counts["ranking_microseconds"] += round((perf_counter()-begin)*1e6)
    return ranked


def shortlist(previews, key, n):
    return sorted(previews, key=lambda p: (p.uses_fallback, round(getattr(p, key), 9),
                                           orders_id(p.move.orders)))[:n]


def move_record(preview, outcome, start):
    p = preview
    return {"id": orders_id(p.move.orders), "kind": p.move.kind, "requests": p.move.requests,
            "vehicles": [v+1 for v in p.move.touched], "feasible": outcome is not None,
            "preview": {"service": p.service, "neutral": p.neutral, "guided": p.guided,
                        "fallback": p.uses_fallback},
            "delta": score_delta(start[1], outcome[1]) if outcome else None}


def run_search(instance, config, seed, method, initial, remaining_seconds):
    begin = perf_counter()
    deadline = begin + max(0.0, remaining_seconds)
    routing_deadline = begin + (max(0.0, remaining_seconds)*config["routing_fraction_B2"]
                               if method == "B2" else max(0.0, remaining_seconds))
    priced = method in ("B3", "P")
    key = {"B1": "service", "B2": "service", "B3": "neutral", "P": "guided"}[method]
    decoder = Decoder(instance, config)
    rng = Random(seed ^ 0x93A1)
    current = best = initial
    traces = []
    orders = passenger_orders(instance, current[0])
    recoded = decoder.decode(orders, priced, routing_deadline)
    if recoded and metric(recoded[1], priced) < metric(current[1], priced)-EPS:
        traces.append({"kind": "fixed_order_initial", "delta": score_delta(current[1], recoded[1])})
        current = best = recoded

    stalls = 0
    completed = 0
    for batch in range(config["iterations"]):
        if perf_counter() >= routing_deadline:
            break
        orders = passenger_orders(instance, current[0])
        moves = proposals(instance, current[0], orders, rng, config["proposals_per_batch"], routing_deadline)
        previews = preview_moves(instance, decoder, current, moves, routing_deadline)
        blind = shortlist(previews, "neutral", config["shortlist"])
        guided = shortlist(previews, "guided", config["shortlist"])
        picked = shortlist(previews, key, config["shortlist"])
        record = {"kind": "paired_batch", "iteration": batch, "parent": orders_id(orders),
                  "proposals": len(moves), "ranked": len(previews), "shortlist_changed": blind != guided,
                  "first_changed": blind[:1] != guided[:1],
                  "blind_ids": [orders_id(p.move.orders) for p in blind],
                  "guided_ids": [orders_id(p.move.orders) for p in guided],
                  "evaluated": [], "accepted": None}
        preferred = None
        for p in picked:
            if perf_counter() >= routing_deadline:
                break
            result = decoder.decode(p.move.orders, priced, routing_deadline)
            row = move_record(p, result, current)
            record["evaluated"].append(row)
            if result and (preferred is None or
                           metric(result[1], priced) < metric(preferred[0][1], priced)-EPS):
                preferred = result, row
        if preferred:
            result, row = preferred
            delta = metric(result[1], priced)-metric(current[1], priced)
            # Small bounded perturbation after stalled batches. Best feasible stays protected.
            kick = stalls >= 2 and batch % 4 == 3 and delta <= max(0.25, 0.01*metric(current[1], priced))
            if delta < -EPS or kick:
                record["accepted"] = {**row, "perturbation": delta >= -EPS,
                                      "guided_only": row["id"] not in record["blind_ids"]}
                current = result
                if metric(current[1], priced) < metric(best[1], priced)-EPS:
                    best = current
                    stalls = 0
                else:
                    stalls += 1
            else:
                stalls += 1
        else:
            stalls += 1
        traces.append(record)
        completed += 1
    if method == "B2":
        result = decoder.decode(passenger_orders(instance, best[0]), True, deadline)
        if result and result[1].metrics.objective_eur < best[1].metrics.objective_eur - EPS:
            traces.append({"kind": "fixed_order_final", "delta": score_delta(best[1], result[1])})
            best = result
    audited = evaluate(instance, best[0])
    decoder.counts["independent_replays"] += 1
    elapsed = perf_counter()-begin
    return (best[0], audited), {"search_seconds": elapsed, "budget_hit": elapsed >= remaining_seconds,
                                "routing_deadline_hit": completed < config["iterations"],
                                "iterations": completed, "trace": traces, "counts": dict(decoder.counts)}


def diagnostic(instance, config, seed, initial):
    begin = perf_counter()
    deadline = begin+config["diagnostic_seconds"]
    decoder = Decoder(instance, config)
    rng = Random(seed ^ 0x93A1)
    order = passenger_orders(instance, initial[0])
    fixed = decoder.decode(order, True, deadline)
    current = fixed if fixed and metric(fixed[1], True) < metric(initial[1], True)-EPS else initial
    paired = []
    for batch in range(config["diagnostic_batches"]):
        if perf_counter() >= deadline:
            break
        moves = proposals(instance, current[0], order, rng, config["proposals_per_batch"], deadline)
        previews = preview_moves(instance, decoder, current, moves, deadline)
        blind = shortlist(previews, "neutral", config["shortlist"])
        guided = shortlist(previews, "guided", config["shortlist"])
        interleaved = [p for pair in zip(blind, guided) for p in pair]
        evaluated = {}
        for p in dict.fromkeys(interleaved):
            if perf_counter() >= deadline:
                break
            checked = decoder.decode(p.move.orders, True, deadline)
            row = move_record(p, checked, current)
            evaluated[row["id"]] = row
        bid = [orders_id(p.move.orders) for p in blind]
        gid = [orders_id(p.move.orders) for p in guided]
        def best(ids):
            return min((evaluated[i]["delta"]["objective_eur"] for i in ids
                        if i in evaluated and evaluated[i]["delta"] is not None), default=None)
        paired.append({"iteration": batch, "proposals": len(moves), "ranked": len(previews),
                       "blind_ids": bid, "guided_ids": gid, "overlap": len(set(bid) & set(gid)),
                       "blind_best": best(bid), "guided_best": best(gid),
                       "evaluated": list(evaluated.values())})
    return {"seconds": perf_counter()-begin, "fixed_order_delta": score_delta(initial[1], current[1]),
            "fixed_order_feasible": fixed is not None, "batches": paired, "counts": dict(decoder.counts)}
