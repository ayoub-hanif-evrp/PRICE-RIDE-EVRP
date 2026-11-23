from dataclasses import replace

import pytest

from price_ride.domain import ChargeEvent, Request, Route, Schedule, Stop
from price_ride.evaluation import evaluate
from price_ride.optimization.structural import closure, inspect, incompatible_pair


def replay(tiny, a, vehicle=1):
    return evaluate(tiny, Schedule((Route(vehicle, tuple(a)), Route(2, (Stop(4), Stop(6))))))


def test_non_integer_vehicle_is_invalid(tiny):
    result = replay(tiny, tuple(Stop(x) for x in (3, 1, 2, 5)), vehicle=True)
    assert not result.feasible and "vehicle_id" in {x.code for x in result.violations}


def test_nonfinite_time_and_charge(tiny):
    checked = replay(tiny, (Stop(3), Stop(1, service_start=float("inf")), Stop(2),
                            Stop(7, charge=ChargeEvent(float("nan"), 1)), Stop(5)))
    assert not checked.feasible
    assert {"causality", "charge_rate"} <= {v.code for v in checked.violations}


def test_signed_nonmetric_excess_survives_replay(tiny):
    nodes = (*tiny.nodes[:6], replace(tiny.nodes[6], load=1), replace(tiny.nodes[7], load=-1))
    matrix = [list(row) for row in tiny.matrix]
    matrix[0][1] = 30
    instance = replace(tiny, nodes=nodes, matrix=tuple(tuple(r) for r in matrix), stations=(),
                       vehicles=(replace(tiny.vehicles[0], initial_kwh=12), tiny.vehicles[1]),
                       requests=(*tiny.requests, Request(2, 7, 8, 60)))
    checked = replay(instance, (Stop(3), Stop(1), Stop(7), Stop(8), Stop(2), Stop(5)))
    assert checked.feasible
    first = next(r for r in checked.rides if r.request == 1)
    assert first.excess_minutes == pytest.approx(-24)
    assert closure(instance.matrix)[0, 1] < 30


def test_zero_energy_visit_still_wastes_a_slot(tiny):
    a = Route(1, tuple(Stop(x, charge=ChargeEvent(0, 0) if x == 7 else None)
                       for x in (3, 1, 2, 7, 5)))
    b = Route(2, (Stop(4), Stop(7, charge=ChargeEvent(2, 1)), Stop(6)))
    assert "station_visit" in {v.code for v in evaluate(tiny, Schedule((a, b))).violations}


def test_active_bound_preserves_zero_idle_arcs(tiny):
    instance = replace(tiny, vehicles=tuple(replace(v, final_ratio=2/3) for v in tiny.vehicles),
                       stations=tiny.stations[:1])
    audited = inspect(instance)
    assert audited["active_upper"] == 1
    assert audited["charge_upper_kwh"] == pytest.approx(15)
    assert all(v["idle_arc_minutes"] == 0 for v in audited["battery"])
    assert audited["travel_lower_minutes"] == pytest.approx(4)


def test_workload_and_pair_conflicts_can_prove_impossibility(tiny):
    nodes = list(tiny.nodes)
    for i, load in ((1, 1), (2, -1), (7, 1), (8, -1)):
        start = 5 if load > 0 else 15
        nodes[i-1] = replace(nodes[i-1], earliest=start, latest=start+0.01, service=2, load=load)
    instance = replace(tiny, nodes=tuple(nodes), requests=(*tiny.requests, Request(2, 7, 8, 60)),
                       stations=(), vehicles=tuple(replace(v, final_ratio=2/3) for v in tiny.vehicles))
    proof = incompatible_pair(instance, *instance.requests, closure(instance.matrix))
    assert proof and len(proof) == 6
    assert inspect(instance)["status"] == "provably infeasible"
