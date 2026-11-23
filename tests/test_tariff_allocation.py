from dataclasses import replace

import pytest

from price_ride.domain import ChargeEvent, Route, Schedule, Stop
from price_ride.evaluation import allocate, evaluate


@pytest.mark.parametrize(("start", "end", "periods"), [
    (14, 15, [0]), (15, 16, [1]), (14, 16, [0, 1]), (29, 31, [1, 2]), (1439, 1440, [95]),
    (0, 1440, list(range(96))),
])
def test_half_open_intervals(tiny, start, end, periods):
    allocations = allocate(tiny, [(tiny.stations[0], 1, 0, start, end, .5)])
    assert [a.period for a in allocations] == periods
    assert sum(a.grid_kwh+a.lec_kwh for a in allocations) == pytest.approx((end-start)*.5)


def test_simultaneous_fleet_surplus_shared(tiny):
    station = replace(tiny.stations[0], node_ids=(7, 8), max_visits=2)
    instance = replace(tiny, stations=(station,))
    event = ChargeEvent(2, 1)
    a = Route(1, (Stop(3), Stop(1), Stop(2), Stop(7, 10, charge=event), Stop(5)))
    b = Route(2, (Stop(4), Stop(8, 10, charge=event), Stop(6)))
    report = evaluate(instance, Schedule((a, b)))
    assert report.feasible
    assert report.metrics.lec_kwh == 1 and report.metrics.grid_kwh == 1
    assert [allocation.lec_kwh for allocation in report.allocations] == [.5, .5]
    assert report.metrics.energy_eur == pytest.approx(.3)


def test_fleet_does_not_reuse_a_station_node(tiny):
    a = Route(1, (Stop(3), Stop(1), Stop(2), Stop(7), Stop(5)))
    b = Route(2, (Stop(4), Stop(7), Stop(6)))
    report = evaluate(tiny, Schedule((a, b)))
    assert "station_visit" in {v.code for v in report.violations}
