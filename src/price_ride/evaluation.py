"""Independent chronological replay and fleet tariff allocation."""
from collections import Counter, defaultdict
from math import floor, isfinite

from price_ride.domain import (ChargeAllocation, EvaluationReport, Metrics, Ride,
                               StopState, VehicleState, Violation)

EPS = 1e-7


def allocate(instance, sessions):
    """Allocate each station's interval supply once over the entire fleet."""
    grouped = defaultdict(list)
    width = instance.electricity.minutes_per_period
    for station, vehicle, stop, start, end, rate in sessions:
        while start < end:
            period = floor(start / width)
            finish = min(end, (period+1)*width)
            grouped[station, period].append((vehicle, stop, start, finish, (finish-start)*rate))
            start = finish
    output = []
    for (station, period), pieces in sorted(grouped.items(), key=lambda row: (row[0][0].id, row[0][1])):
        demand = sum(piece[-1] for piece in pieces)
        fraction = min(1.0, station.surplus[period] / demand)
        for vehicle, stop, start, end, kwh in pieces:
            lec = kwh * fraction
            grid = kwh - lec
            cost = lec * station.mmr[period] + grid * instance.electricity.grid[period]
            output.append(ChargeAllocation(station.id, period, vehicle, stop, start, end, grid, lec, cost))
    return tuple(output)


def evaluate(instance, schedule):
    violations, states, rides, sessions = [], [], [], []
    pickups = {r.pickup: r for r in instance.requests}
    dropoffs = {r.dropoff: r for r in instance.requests}
    stations = {i: s for s in instance.stations for i in s.node_ids}
    vehicles = {v.id: v for v in instance.vehicles}
    vehicle_counts = Counter(route.vehicle for route in schedule.routes)
    served_pickups, served_dropoffs = Counter(), Counter()
    visited_station_nodes, fleet_visits = set(), Counter()
    travel = service = waiting = charging = 0.0

    def flag(code, explanation, vehicle=None, stop=None, request=None, magnitude=None):
        violations.append(Violation(code, explanation, vehicle, request, stop, magnitude))

    for v in instance.vehicles:
        if vehicle_counts[v.id] != 1:
            flag("vehicle_count", "vehicle needs exactly one route", v.id,
                 magnitude=abs(vehicle_counts[v.id]-1))
    for route in schedule.routes:
        vehicle = vehicles.get(route.vehicle)
        if vehicle is None:
            flag("vehicle_id", "unknown vehicle", route.vehicle)
            continue
        vid = vehicle.id
        if (len(route.stops) < 2 or route.stops[0].node != vehicle.origin
                or route.stops[-1].node != vehicle.destination):
            flag("depots", "route must start and end at the assigned depots", vid)
        picked, onboard = set(), {}
        used_stations = []
        soc = minimum = vehicle.initial_kwh
        clock = 0.0
        load = 0
        prior = None
        route_states = []
        complete_clock = True
        for index, stop in enumerate(route.stops):
            try:
                node = instance.node(stop.node)
            except ValueError as exc:
                flag("node", str(exc), vid, index)
                complete_clock = False
                break
            request = pickups.get(node.id) or dropoffs.get(node.id)
            station = stations.get(node.id)
            if request is None and station is None and (
                    (index != 0 or node.id != vehicle.origin) and
                    (index != len(route.stops)-1 or node.id != vehicle.destination)):
                flag("depot_stop", "depot used outside its permitted route endpoint", vid, index)

            if prior is not None:
                minutes = instance.travel(prior, node.id)
                if not isfinite(minutes) or minutes < 0:
                    flag("arc", f"unreachable or invalid arc {prior} → {node.id}", vid, index)
                    complete_clock = False
                    break
                travel += minutes
                clock += minutes
                soc -= minutes * instance.consumption
                minimum = min(minimum, soc)
                if soc < -EPS:
                    flag("battery_shortfall", "arrival energy below zero", vid, index, magnitude=-soc)
            arrival, arrival_soc = clock, soc
            start = max(arrival, node.earliest)
            if stop.service_start is not None:
                desired = stop.service_start
                if not isfinite(desired) or desired < arrival - EPS:
                    flag("causality", "service start precedes arrival or is nonfinite", vid, index,
                         magnitude=arrival-desired if isfinite(desired) else None)
                else:
                    start = max(arrival, desired)
            if start < node.earliest - EPS or start > node.latest + EPS:
                flag("time_window", "service start outside node window", vid, index,
                     request.id if request else None, max(node.earliest-start, start-node.latest))
            waiting += start - arrival
            service += node.service
            clock = start + node.service

            if node.id in pickups:
                rid = request.id
                served_pickups[rid] += 1
                if rid in picked:
                    flag("duplicate_pickup", "request picked up twice on route", vid, index, rid)
                else:
                    onboard[rid] = clock
                    picked.add(rid)
            if node.id in dropoffs:
                rid = request.id
                served_dropoffs[rid] += 1
                if rid not in onboard:
                    flag("precedence", "no prior unmatched pickup on this vehicle", vid, index, rid)
                else:
                    pickup = onboard.pop(rid)
                    duration = start - pickup
                    excess = duration - instance.travel(request.pickup, request.dropoff)
                    rides.append(Ride(rid, vid, pickup, start, duration,
                                      0.0 if abs(excess) <= EPS else excess))
                    if duration > request.max_ride + EPS:
                        flag("ride_time", "on-board ride limit exceeded", vid, index, rid,
                             duration-request.max_ride)
            load += node.load
            if not 0 <= load <= vehicle.capacity:
                flag("load", "occupancy outside vehicle limits", vid, index,
                     request.id if request else None, max(-load, load-vehicle.capacity))

            if station:
                used_stations.append(station.id)
                fleet_visits[station.id] += 1
                if fleet_visits[station.id] > station.max_visits or node.id in visited_station_nodes:
                    flag("station_visit", "fleet visit limit exceeded or station copy reused", vid, index,
                         magnitude=max(1, fleet_visits[station.id]-station.max_visits))
                visited_station_nodes.add(node.id)
                if load:
                    flag("passengers_at_station", "vehicle must be empty when visiting a station", vid, index,
                         magnitude=abs(load))
            if stop.charge is not None:
                event = stop.charge
                values = (event.kwh, event.duration, event.wait_before)
                if station is None:
                    flag("charge_location", "charge event outside a charging station", vid, index)
                elif (not all(isfinite(v) and v >= 0 for v in values) or
                      (event.duration == 0 and event.kwh > 0) or
                      (event.duration > 0 and event.kwh / event.duration > station.rate + EPS)):
                    flag("charge_rate", "invalid charge energy, duration, wait or rate", vid, index)
                else:
                    waiting += event.wait_before
                    clock += event.wait_before
                    end = clock + event.duration
                    if event.kwh > 0:
                        if clock < 0 or end > instance.horizon + EPS or end <= clock:
                            flag("charge_horizon", "charge event outside available periods", vid, index)
                        else:
                            billed_end = min(end, instance.horizon)
                            sessions.append((station, vid, index, clock, billed_end,
                                             event.kwh / event.duration))
                    clock = end
                    charging += event.duration
                    soc += event.kwh
                    if soc > vehicle.battery_kwh + EPS:
                        flag("battery_overfill", "charged beyond battery capacity", vid, index,
                             magnitude=soc-vehicle.battery_kwh)
            if not isfinite(stop.wait_after) or stop.wait_after < 0:
                flag("waiting", "post-service wait must be finite and nonnegative", vid, index)
            else:
                waiting += stop.wait_after
                clock += stop.wait_after
            route_states.append(StopState(node.id, arrival, start, clock, load, arrival_soc, soc,
                                          tuple(sorted(onboard)), node.latest-start))
            prior = node.id

        if load or onboard:
            flag("return_load", "vehicle returns with unmatched passengers", vid, magnitude=abs(load))
        for rid in sorted(onboard):
            flag("unfinished_ride", "picked-up passenger has no later dropoff on this vehicle", vid,
                 request=rid)
        reserve = vehicle.final_ratio * vehicle.battery_kwh
        if complete_clock and soc < reserve - EPS:
            flag("final_soc", "destination reserve violated", vid, magnitude=reserve-soc)
        if clock > instance.horizon + EPS:
            flag("horizon", "route finishes after the horizon", vid, magnitude=clock-instance.horizon)
        states.append(VehicleState(vid, tuple(route_states), vehicle.initial_kwh, soc, minimum,
                                   tuple(used_stations), complete_clock and clock <= instance.horizon+EPS))

    for request in instance.requests:
        for kind, counts in (("pickup", served_pickups), ("dropoff", served_dropoffs)):
            count = counts[request.id]
            if count != 1:
                flag(f"{kind}_count", f"{kind} appears {count} times", request=request.id,
                     magnitude=abs(count-1))
    allocations = allocate(instance, sessions)
    grid = sum(a.grid_kwh for a in allocations)
    lec = sum(a.lec_kwh for a in allocations)
    energy = sum(a.cost_eur for a in allocations)
    excess = sum(r.excess_minutes for r in rides)
    objective = instance.objective
    car, user = travel*objective.travel_eur_per_min, excess*objective.excess_eur_per_min
    metrics = Metrics(travel, excess, service, waiting, charging, grid+lec, grid, lec, car, user,
                      energy, car+user+energy,
                      travel*objective.legacy_weights[0] + excess*objective.legacy_weights[1])
    return EvaluationReport(not violations, tuple(violations), tuple(states), tuple(rides),
                            allocations, metrics)
