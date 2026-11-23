"""Seeded paired insertion, bounded restarts and complete-order moves."""
from dataclasses import dataclass
from itertools import combinations
from random import Random
from time import perf_counter

from price_ride.optimization.charging import Decoder
from price_ride.optimization.timing import Timing

Orders = tuple[tuple[int, ...], ...]


@dataclass(frozen=True)
class Move:
    kind: str
    requests: tuple[int, ...]
    orders: Orders
    touched: tuple[int, ...]


def passenger_orders(instance, schedule):
    stations = {n for s in instance.stations for n in s.node_ids}
    return tuple(tuple(s.node for s in r.stops if s.node not in stations)
                 for r in sorted(schedule.routes, key=lambda x: x.vehicle))


def remove(order, request):
    return tuple(n for n in order if n not in (request.pickup, request.dropoff))


def insertions(instance, order, request, vehicle, limit, deadline):
    """Generate the best few time-feasible pair insertions under a cheap service score."""
    pickup, dropoff = request.pickup, request.dropoff
    pickup_node, dropoff_node = instance.node(pickup), instance.node(dropoff)
    travel = instance.travel
    nodes = [instance.node(i) for i in order]
    p_positions, d_positions = [], []
    for i, (before, after) in enumerate(zip(nodes, nodes[1:]), 1):
        for new, positions in ((pickup_node, p_positions), (dropoff_node, d_positions)):
            if before.earliest+before.service+travel(before.id, new.id) <= new.latest+1e-7:
                positions.append(i)
    trials = []
    for p in p_positions:
        a, b = order[p-1:p+1]
        for d in d_positions:
            if d <= p:
                continue
            c, e = order[d-1:d+1]
            delta = (travel(a, pickup)+travel(pickup, b)-travel(a, b) +
                     travel(c, dropoff)+travel(dropoff, e)-travel(c, e))
            trials.append((delta, p, d))
        delta = travel(a, pickup)+travel(pickup, dropoff)+travel(dropoff, b)-travel(a, b)
        trials.append((delta, p, p))
    options = []
    for _, p, d in sorted(trials):
        if perf_counter() >= deadline:
            break
        candidate = order[:p]+(pickup,)+order[p:d]+(dropoff,)+order[d:]
        timing = Timing(instance, candidate, vehicle)
        ready = timing.schedule({})
        if ready is None:
            continue
        obj = instance.objective
        score = timing.travel*obj.travel_eur_per_min + ready[1]*obj.excess_eur_per_min
        options.append((score, candidate))
        if len(options) >= limit:
            break
    return sorted(options)


def replace_orders(orders, changes):
    return tuple(changes.get(i, order) for i, order in enumerate(orders))


def equivalent_idle(instance, orders, order_of_vehicles):
    """Deduplicate empty routes whose vehicle data, arcs and depot windows agree."""
    seen = set()
    for i in order_of_vehicles:
        order, v = orders[i], instance.vehicles[i]
        if len(order) == 2:
            start, end = instance.node(v.origin), instance.node(v.destination)
            key = (v.capacity, v.initial_kwh, v.battery_kwh, v.final_ratio,
                   (start.service, start.earliest, start.latest), (end.service, end.earliest, end.latest),
                   instance.matrix[v.origin-1], tuple(row[v.destination-1] for row in instance.matrix))
            if key in seen:
                continue
            seen.add(key)
        yield i


def randomized_start(instance, config, seed, seconds, fallback=None):
    """Several chronological-jitter orders, with bounded restart repair of missed pairs."""
    begin = perf_counter()
    deadline = begin+seconds
    rng = Random(seed)
    decoder = Decoder(instance, config)
    vehicles = instance.vehicles
    starts, forced = [], set()
    empties = tuple((v.origin, v.destination) for v in vehicles)
    best_partial = None
    for attempt in range(3):
        if perf_counter() >= deadline:
            break
        def request_key(request):
            return (request.id not in forced,
                    instance.node(request.pickup).earliest+rng.uniform(-18, 18))
        queue = sorted(instance.requests, key=request_key)
        priority = list(range(len(vehicles)))
        rng.shuffle(priority)
        orders = empties
        unresolved = []
        for request in queue:
            if perf_counter() >= deadline:
                unresolved.append(request.id)
                continue
            routes = []
            for i in equivalent_idle(instance, orders, priority):
                base = Timing(instance, orders[i], vehicles[i]).travel
                for score, changed in insertions(instance, orders[i], request, vehicles[i], 2, deadline):
                    routes.append((score-base*instance.objective.travel_eur_per_min, i, changed))
            # Try best marginal insertions, with a seeded perturbation of their order.
            routes = sorted(routes, key=lambda x: x[0])
            candidates = routes[:6]
            if len(candidates) > 1 and rng.random() < 0.25:
                j = rng.randrange(1, min(3, len(candidates)))
                candidates[0], candidates[j] = candidates[j], candidates[0]
            for _, i, route in candidates:
                trial = replace_orders(orders, {i: route})
                if decoder.decode(trial, False, deadline, replay=False) is not None:
                    orders = trial
                    break
            else:
                unresolved.append(request.id)
        starts.append({"request_order": [r.id for r in queue], "vehicle_order": [i+1 for i in priority],
                       "unserved": unresolved, "orders": orders})
        if best_partial is None or len(unresolved) < len(best_partial["unserved"]):
            best_partial = starts[-1]
        if not unresolved:
            outcome = decoder.decode(orders, False, deadline)
            if outcome is not None:
                return outcome, {"source": "randomized paired insertion", "runtime_seconds": perf_counter()-begin,
                                 "attempts": starts, "counts": dict(decoder.counts)}
        # Missed requests get priority in the following independently perturbed pass.
        forced = set(unresolved[:3])
    found = fallback is not None and fallback[1].feasible
    return (fallback if found else None), {
        "source": "verified historical fallback" if found else "no complete feasible start",
        "runtime_seconds": perf_counter()-begin, "attempts": starts,
        "best_partial_unserved": best_partial["unserved"] if best_partial else None,
        "counts": dict(decoder.counts)}


def proposals(instance, schedule, orders, rng, cap, deadline):
    by_pickup = {r.pickup: r for r in instance.requests}
    assignments = [(i, by_pickup[n]) for i, order in enumerate(orders) for n in order if n in by_pickup]
    stations = {node for s in instance.stations for node in s.node_ids}
    nearby = []
    for i, route in enumerate(schedule.routes):
        for pos, stop in enumerate(route.stops):
            if stop.node in stations and stop.charge:
                gap_neighbors = route.stops[max(0, pos-5):pos]+route.stops[pos+1:pos+6]
                ids = {s.node for s in gap_neighbors}
                nearby.extend((i, r) for j, r in assignments if i == j and
                              (r.pickup in ids or r.dropoff in ids))
    moves = {}
    vehicles = instance.vehicles
    if not assignments:
        return []
    for draw in range(cap*2):
        if len(moves) >= cap or perf_counter() >= deadline:
            break
        i, request = rng.choice(nearby if nearby and draw % 3 != 0 else assignments)
        targets = list(equivalent_idle(instance, orders, range(len(orders))))
        j = rng.choice(targets)
        donor = remove(orders[i], request)
        if i != j and draw % 3 == 1 and len(orders[j]) > 2:
            second = rng.choice([r for k, r in assignments if k == j])
            a = insertions(instance, donor, second, vehicles[i], 2, deadline)
            b = insertions(instance, remove(orders[j], second), request, vehicles[j], 2, deadline)
            if a and b:
                new = replace_orders(orders, {i: a[0][1], j: b[0][1]})
                moves[new] = Move("paired_exchange", (request.id, second.id), new, tuple(sorted((i, j))))
            continue
        target = donor if i == j else orders[j]
        for _, inserted in insertions(instance, target, request, vehicles[j], 3, deadline):
            changes = {i: donor, j: inserted}
            new = replace_orders(orders, changes)
            if new != orders:
                moves[new] = Move("pair_reinsert" if i == j else "paired_relocation", (request.id,),
                                  new, tuple(sorted(changes)))
            if len(moves) >= cap:
                break
    return list(moves.values())
