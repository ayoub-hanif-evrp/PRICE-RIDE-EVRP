from dataclasses import replace
from random import Random
from time import perf_counter

import numpy as np
import pytest
from scipy.optimize import linprog

from price_ride.domain import ChargeEvent, Request, TimeSeries
from price_ride.optimization.charging import Decoder, interval_starts, periods
from price_ride.optimization.orders import Move, insertions, passenger_orders, proposals
from price_ride.optimization.search import preview_moves, shortlist
from price_ride.optimization.timing import Timing


@pytest.fixture
def settings():
    return {"two_charge_layouts": 24, "pool_per_slot_signature": 4, "fleet_combinations": 4096}


def test_pickup_delay_matches_lp_on_microcase(tiny):
    drop_window = replace(tiny.nodes[1], earliest=40)
    instance = replace(tiny, nodes=(tiny.nodes[0], drop_window, *tiny.nodes[2:]))
    t = Timing(instance, (3, 1, 2, 5), tiny.vehicles[0])
    route, excess = t.schedule({})
    objective = (0, -1, 1, 0)
    inequalities = np.zeros((4, 4))
    for i in range(3):
        inequalities[i, i] = 1
        inequalities[i, i+1] = -1
    inequalities[3, 1], inequalities[3, 2] = -1, 1
    rhs = [-x for x in t._weights({})] + [tiny.requests[0].max_ride+t.service[1]]
    cert = linprog(objective, A_ub=inequalities, b_ub=rhs,
                   bounds=list(zip(t.lower, t.upper)), method="highs")
    assert cert.success
    assert route.stops[1].service_start > t.bounds({})[0][1]
    assert excess == pytest.approx(cert.fun-t.service[1]-tiny.travel(1, 2))


def test_sampled_boundaries_and_horizon():
    assert {7, 15, 22, 30} <= set(interval_starts(4, 40, 8, 15, 1440))
    assert list(periods(1439, ChargeEvent(1, .4), 15, 1440)) == [(95, .4)]
    assert list(periods(14, ChargeEvent(2, 1), 15, 1440)) == [(0, .5), (1, .5)]


def test_two_charges_when_single_cannot_reach_reserve(tiny, settings):
    a = replace(tiny.vehicles[0], battery_kwh=8, initial_kwh=5, final_ratio=3/8)
    instance = replace(tiny, vehicles=(a, tiny.vehicles[1]), consumption=1)
    decoder = Decoder(instance, settings)
    orders = ((3, 1, 2, 5), (4, 6))
    schedule, report = decoder.decode(orders, True, perf_counter()+2)
    assert report.feasible
    assert sum(s.charge is not None for s in schedule.routes[0].stops) == 2
    assert report.metrics.charged_kwh == pytest.approx(8)
    assert report.vehicles[0].final_kwh == pytest.approx(3)
    assert report.metrics.charged_kwh == pytest.approx(report.metrics.travel_minutes-2)


def test_grid_microcase_matches_integer_oracle(tiny, settings):
    v = replace(tiny.vehicles[0], final_ratio=2/3)
    instance = replace(tiny, vehicles=(v,tiny.vehicles[1]))
    decoder = Decoder(instance, settings)
    clock = perf_counter()+4
    order = (3, 1, 2, 5)
    stop, = instance.stations[:1]
    ids = (3, 1, 2, stop.id, 5)
    vehicle = instance.vehicles[0]
    timing = Timing(instance, ids, vehicle)
    event = {3: ChargeEvent(8, 4)}
    viable = [decoder.option(timing, event, {3: t}) for t in range(10, 90)]
    actual = decoder.layout_options(ids, (3,), vehicle, True, False, clock, None)
    assert min(decoder.bill(o.demand) for o in actual) == pytest.approx(
        min(decoder.bill(o.demand) for o in viable if o is not None))
    x, report = decoder.decode((order, (4, 6)), True, clock)
    assert report.feasible and passenger_orders(instance, x) == (order, (4, 6))


def test_fleet_copy_pool_conflict_and_finite_price(tiny, settings):
    v = tuple(replace(x, final_ratio=2/3) for x in tiny.vehicles)
    decoder = Decoder(replace(tiny, vehicles=v), settings)
    first, second = (
        decoder.options(1, (3, 1, 2, 5), True, perf_counter()+2),
        decoder.options(2, (4, 6), True, perf_counter()+2),
    )
    checked = decoder._compatible((first, second), True, perf_counter()+2)
    assert checked is not None
    o = next(o for o in first if o.slots)
    assert decoder._compatible(((o,), (o,)), True, perf_counter()+2) is None
    assert decoder.bill([(7, 0, 1.0), (7, 0, 1.0)]) == pytest.approx(.3)


def test_reassignment_and_neutral_equivalence_under_flat_grid(tiny, settings):
    no_surplus = tuple(replace(s, surplus=(0,)*96) for s in tiny.stations)
    instance = replace(tiny, stations=no_surplus, electricity=TimeSeries(15, (.2,)*96))
    decoder = Decoder(instance, settings)
    orders = ((3, 1, 2, 5), (4, 6))
    current = decoder.decode(orders, True, perf_counter()+2)
    alternate = ((3, 5), (4, 1, 2, 6))
    move = Move("paired_relocation", (1,), alternate, (0, 1))
    options = proposals(instance, current[0], orders, Random(11), 10, perf_counter()+2)
    assert alternate in {p.orders for p in options}
    assert insertions(instance, (4, 6), instance.requests[0], instance.vehicles[1],
                      3, perf_counter()+2)[0][1] == alternate[1]
    previews = preview_moves(instance, decoder, current, [move], perf_counter()+2)
    assert previews[0].guided == previews[0].neutral
    assert shortlist(previews, "guided", 1) == shortlist(previews, "neutral", 1)
