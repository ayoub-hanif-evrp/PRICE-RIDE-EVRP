"""Fixed-order route options and global station allocation for the strict contract."""
from collections import Counter, defaultdict
from dataclasses import dataclass
from itertools import combinations_with_replacement, product
from math import ceil, floor, fsum
from time import perf_counter

from price_ride.domain import ChargeEvent, Route, Schedule
from price_ride.evaluation import EPS, evaluate
from price_ride.optimization.timing import Timing


@dataclass(frozen=True)
class Option:
    route: Route
    travel: float
    excess: float
    service_cost: float
    kwh: float
    slots: tuple[int, ...]
    demand: tuple[tuple[int, int, float], ...]


def periods(start, event, width, horizon):
    """KWh held continuously from start through the charge's actual finish."""
    end = min(start+event.duration, horizon)
    if event.kwh <= 0 or end <= start:
        return
    i = floor(start/width)
    while start < end:
        finish = min(end, (i+1)*width)
        yield i, event.kwh*(finish-start)/event.duration
        i += 1
        start = finish


def interval_starts(first, last, duration, width, horizon):
    if first > last + EPS:
        return ()
    last = max(first, min(last, horizon-duration))
    cuts = {first, last, (first+last)/2}
    for offset in (0.0, duration):
        begin = ceil((first+offset)/width)
        end = floor((last+offset)/width)
        cuts.update(i*width-offset for i in range(begin, end+1))
    return tuple(sorted(cuts))


class Decoder:
    def __init__(self, instance, config):
        self.instance = instance
        self.vehicles = {v.id: v for v in instance.vehicles}
        self.by_node = {n: s for s in instance.stations for n in s.node_ids}
        self.by_site = {s.id: s for s in instance.stations}
        self.grid = instance.electricity.grid
        self.reference = self.grid[0] if min(self.grid) == max(self.grid) else fsum(self.grid)/len(self.grid)
        self.config = config
        self.cache = {}
        self.counts = Counter()

    def bill(self, demands, residual=None):
        quantities = defaultdict(float)
        for site, interval, amount in demands:
            quantities[site, interval] += amount
        return fsum(self.incremental(site, period, amount, residual)
                    for (site, period), amount in quantities.items())

    def incremental(self, site, period, amount, residual):
        station = self.by_site[site]
        remaining = (station.surplus[period] if residual is None else
                     residual.get((site, period), station.surplus[period]))
        local = min(amount, remaining)
        return local*station.mmr[period]+(amount-local)*self.grid[period]

    def option(self, timing, charges, fixed):
        result = timing.schedule(charges, fixed)
        if result is None:
            return None
        route, excess = result
        instance = self.instance
        demands = []
        for i, event in charges.items():
            stop = route.stops[i]
            start = stop.service_start+timing.service[i]
            demands.extend((self.by_node[stop.node].id, t, q) for t, q in periods(
                start, event, instance.electricity.minutes_per_period, instance.horizon))
        cost = (timing.travel*instance.objective.travel_eur_per_min +
                excess*instance.objective.excess_eur_per_min)
        return Option(route, timing.travel, excess, cost, sum(c.kwh for c in charges.values()),
                      tuple(timing.ids[i] for i in charges), tuple(demands))

    def energy_plans(self, timing, vehicle, indices):
        """Return one minimum purchase or bounded splits of the minimum purchase."""
        cons = self.instance.consumption
        cumulative = [0.0]
        for arc in timing.arcs:
            cumulative.append(cumulative[-1]+arc*cons)
        start, cap = vehicle.initial_kwh, vehicle.battery_kwh
        reserve = cap*vehicle.final_ratio
        needed = max(0.0, reserve+cumulative[-1]-start)
        if not indices:
            return ((),) if needed <= EPS/2 and start >= cumulative[-1]-EPS/2 else ()
        energy = [cumulative[i] for i in indices]
        at_first = start-energy[0]
        suffix = cumulative[-1]-energy[-1]
        if at_first < -EPS/2 or reserve+suffix > cap+EPS/2 or needed <= EPS:
            return ()
        if len(energy) == 1:
            return ((needed,),) if at_first+needed <= cap+EPS/2 else ()
        middle = energy[1]-energy[0]
        low = max(0.0, middle-at_first, needed-cap)
        high = min(needed, cap-at_first)
        if low > high+EPS/2:
            return ()
        return tuple((q, needed-q) for q in sorted({low, high, (low+high)/2})
                     if q > EPS and needed-q > EPS)

    @staticmethod
    def add_stations(order, placements):
        ids = list(order)
        indices = []
        for gap, node in placements:
            indices.append(gap+len(indices))
            ids.insert(indices[-1], node)
        return tuple(ids), tuple(indices)

    def layouts(self, order, two=False):
        gaps = []
        load = 0
        for gap, node in enumerate(order[:-1], 1):
            load += self.instance.node(node).load
            if load == 0:
                gaps.append(gap)
        if not two:
            return [((gap, node),) for gap in gaps for node in self.by_node]
        layouts = []
        for a, b in combinations_with_replacement(gaps, 2):
            for u, v in product(self.by_node, repeat=2):
                if u != v and (self.by_node[u].id != self.by_node[v].id or self.by_node[u].max_visits > 1):
                    layouts.append(((a, u), (b, v)))
        def route_length(layout):
            ids, _ = self.add_stations(order, layout)
            return sum(self.instance.travel(i, j) for i, j in zip(ids, ids[1:]))
        layouts.sort(key=route_length)
        limit = self.config["two_charge_layouts"]
        self.counts["pruned_two_charge_layouts"] += max(0, len(layouts)-limit)
        return layouts[:limit]

    def layout_options(self, ids, indices, vehicle, priced, preview, deadline, residual):
        timing = Timing(self.instance, ids, vehicle)
        if not timing.valid:
            return []
        methods = []
        width = self.instance.electricity.minutes_per_period
        horizon = self.instance.horizon
        for amounts in self.energy_plans(timing, vehicle, indices):
            if perf_counter() >= deadline:
                break
            charges = {i: ChargeEvent(q/self.by_node[ids[i]].rate, q) for i, q in zip(indices, amounts)}
            if not charges or not priced:
                choice = self.option(timing, charges, {})
                if choice is not None:
                    methods.append(choice)
                continue
            bounds = timing.bounds(charges)
            if bounds is None:
                self.counts["timing_infeasible_layout"] += 1
                continue
            def sample(index, limits):
                lo, hi = timing.window(index, limits)
                event = charges[index]
                site = self.by_node[ids[index]].id
                starts = interval_starts(lo, hi, event.duration, width, horizon)
                if not starts:
                    return ()
                representatives = [starts[0], starts[-1], starts[len(starts)//2]]
                if preview:
                    return tuple(dict.fromkeys(representatives))
                def estimate(t):
                    return fsum(self.incremental(site, p, q, residual)
                                for p, q in periods(t, event, width, horizon))
                ranked = sorted(starts, key=lambda t: (estimate(t), t))
                # Representatives retain endpoints and cheapest sampled periods.
                return tuple(dict.fromkeys([*representatives, *ranked[:3]]))

            for first in sample(indices[0], bounds):
                fixed = {indices[0]: first}
                if len(indices) == 1:
                    choice = self.option(timing, charges, fixed)
                    if choice is not None:
                        methods.append(choice)
                    continue
                second = timing.bounds(charges, fixed)
                if second is None:
                    continue
                for start in sample(indices[1], second):
                    choice = self.option(timing, charges, fixed | {indices[1]: start})
                    if choice is not None:
                        methods.append(choice)
            # Retain an independently replayable timing fallback.
            choice = self.option(timing, charges, {})
            if choice is not None:
                methods.append(choice)
        return methods

    def options(self, vehicle_id, order, priced, deadline, *, preview=False, residual=None):
        key = (vehicle_id, order, priced)
        if not preview and key in self.cache:
            self.counts["option_cache_hits"] += 1
            return self.cache[key]
        begin = perf_counter()
        vehicle = self.vehicles[vehicle_id]
        options = self.layout_options(order, (), vehicle, priced, preview, deadline, residual)
        if not options or len(order) > 2:
            for placements in self.layouts(order):
                if perf_counter() >= deadline:
                    break
                ids, indices = self.add_stations(order, placements)
                options.extend(self.layout_options(ids, indices, vehicle, priced, preview, deadline, residual))
        if not options and not preview and self.instance.stations:
            for placements in self.layouts(order, two=True):
                if perf_counter() >= deadline:
                    break
                ids, indices = self.add_stations(order, placements)
                options.extend(self.layout_options(ids, indices, vehicle, priced, preview, deadline, residual))
        self.counts["route_options"] += len(options)
        self.counts["option_microseconds"] += round((perf_counter()-begin)*1e6)
        if preview:
            return options
        pools = defaultdict(list)
        for option in options:
            pools[tuple(sorted(option.slots))].append(option)
        best = []
        for pool in pools.values():
            pool = list(dict.fromkeys(pool))
            pool.sort(key=lambda o: (o.service_cost+(self.bill(o.demand) if priced else 0), o.kwh,
                                     tuple(stop.service_start for stop in o.route.stops)))
            limit = self.config["pool_per_slot_signature"]
            best.extend(pool[:limit])
            self.counts["options_pruned"] += max(0, len(pool)-limit)
        if perf_counter() < deadline:
            self.cache[key] = tuple(best)
        else:
            self.counts["decoder_deadlines"] += 1
        return tuple(best)

    def _compatible(self, sets, priced, deadline):
        incumbent = None
        for index, combination in enumerate(product(*sets)):
            if perf_counter() >= deadline or index >= self.config["fleet_combinations"]:
                self.counts["fleet_cap_or_deadline"] += 1
                break
            self.counts["fleet_combinations"] += 1
            slots = [s for o in combination for s in o.slots]
            if len(set(slots)) != len(slots):
                self.counts["station_copy_conflicts"] += 1
                continue
            counts = Counter(self.by_node[n].id for n in slots)
            if any(counts[s] > self.by_site[s].max_visits for s in counts):
                self.counts["station_visit_conflicts"] += 1
                continue
            service = sum(o.service_cost for o in combination)
            kwh = sum(o.kwh for o in combination)
            energy = self.bill(q for o in combination for q in o.demand) if priced else 0.0
            key = (service+energy, kwh)
            if incumbent is None or key < incumbent[0]:
                incumbent = key, combination
        return None if incumbent is None else incumbent[1]

    def decode(self, orders, priced, deadline, *, replay=True):
        sets = [self.options(i, order, priced, deadline) for i, order in enumerate(orders, 1)]
        self.counts["fleet_decode_calls"] += 1
        if not all(sets):
            self.counts["no_route_options"] += 1
            return None
        selected = self._compatible(sets, priced, deadline)
        if selected is None:
            self.counts["no_fleet_combination"] += 1
            return None
        schedule = Schedule(tuple(o.route for o in selected))
        if not replay:
            return selected
        result = evaluate(self.instance, schedule)
        self.counts["independent_replays"] += 1
        if not result.feasible:
            self.counts.update(f"replay_{v.code}" for v in result.violations)
            return None
        return schedule, result
