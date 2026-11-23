from dataclasses import replace

import pytest

from price_ride.domain import Request, Route, Schedule, Stop
from price_ride.evaluation import evaluate


def schedule(a=(3, 1, 2, 5), b=(4, 6)):
    return Schedule(tuple(Route(i, tuple(x if isinstance(x, Stop) else Stop(x) for x in route))
                          for i, route in enumerate((a, b), 1)))


def codes(instance, solution):
    return {v.code for v in evaluate(instance, solution).violations}


def test_valid_pair_and_depot_return(tiny):
    report = evaluate(tiny, schedule())
    assert report.feasible
    ride, = report.rides
    assert (ride.pickup_complete, ride.dropoff_start, ride.minutes, ride.excess_minutes) == (5, 7, 2, 0)
    assert report.metrics.travel_minutes == 6
    assert report.metrics.service_minutes == 4
    assert report.metrics.objective_eur == pytest.approx(2.16)
    car, _ = report.vehicles
    assert car.stops[-1].load == 0
    assert car.stops[-1].departure == 10
    assert car.minimum_kwh == car.final_kwh == 7


@pytest.mark.parametrize(("a", "b", "expected"), [
    ((3, 2, 1, 5), (4, 6), {"precedence", "load", "unfinished_ride"}),
    ((3, 1, 5), (4, 2, 6), {"precedence", "unfinished_ride", "return_load"}),
    ((3, 1, 2, 6), (4, 6), {"depots", "depot_stop"}),
    ((3, 1, 2, 1, 2, 5), (4, 6), {"pickup_count", "dropoff_count", "duplicate_pickup"}),
    ((3, 5), (4, 6), {"pickup_count", "dropoff_count"}),
    ((3, 0, 5), (4, 6), {"node"}),
    ((3, 1, 2, 3, 5), (4, 6), {"depot_stop"}),
    ((3, Stop(1, 1), 2, 5), (4, 6), {"causality"}),
    ((3, 1, 2, Stop(5, 1440, wait_after=1)), (4, 6), {"horizon"}),
])
def test_bad_route(tiny, a, b, expected):
    assert expected <= codes(tiny, schedule(a, b))


def test_window(tiny):
    first = replace(tiny.nodes[0], latest=1)
    assert "time_window" in codes(replace(tiny, nodes=(first, *tiny.nodes[1:])), schedule())


def test_ride_time_excludes_service_and_includes_intermediate_waiting(tiny):
    instance = replace(tiny, requests=(replace(tiny.requests[0], max_ride=6),))
    assert evaluate(instance, schedule((3, Stop(1, 4), Stop(2, 13), 5))).rides[0].minutes == 6
    assert "ride_time" in codes(instance, schedule((3, Stop(1, 4, wait_after=3), Stop(2, 14), 5)))


def test_capacity(tiny):
    nodes = tiny.nodes[:6] + (replace(tiny.nodes[6], load=1), replace(tiny.nodes[7], load=-1))
    capacity_one = replace(tiny.vehicles[0], capacity=1)
    instance = replace(tiny, nodes=nodes, requests=(*tiny.requests, Request(2, 7, 8, 60)),
                       vehicles=(capacity_one, tiny.vehicles[1]), stations=())
    assert "load" in codes(instance, schedule((3, 1, 7, 2, 8, 5)))


def test_invalid_arc(tiny):
    matrix = (*tiny.matrix[:2], (float("inf"), *tiny.matrix[2][1:]), *tiny.matrix[3:])
    assert "arc" in codes(replace(tiny, matrix=matrix), schedule())
