from dataclasses import replace

import pytest

from price_ride.domain import ChargeEvent, Route, Schedule, Stop
from price_ride.evaluation import evaluate


def check(instance, charge=None, at=7):
    stops = (Stop(3), Stop(1), Stop(2))
    if charge:
        stops += (Stop(at, charge=charge),)
    report = evaluate(instance, Schedule((Route(1, (*stops, Stop(5))), Route(2, (Stop(4), Stop(6))))))
    return report, {v.code for v in report.violations}


def test_stationary_time_uses_no_traction_energy(tiny):
    route = Route(1, (Stop(3, wait_after=300), Stop(1), Stop(2), Stop(5)))
    report = evaluate(tiny, Schedule((route, Route(2, (Stop(4), Stop(6))))))
    assert report.feasible and report.metrics.waiting_minutes == 300
    assert report.vehicles[0].final_kwh == 7


def test_negative_and_final_soc_are_distinct(tiny):
    first, second = tiny.vehicles
    assert "battery_shortfall" in check(replace(tiny, vehicles=(replace(first, initial_kwh=1), second)))[1]
    assert check(replace(tiny, vehicles=(replace(first, final_ratio=2/3), second)))[1] == {"final_soc"}


def test_charge_to_reserve(tiny):
    first, second = tiny.vehicles
    instance = replace(tiny, vehicles=(replace(first, final_ratio=2/3), second))
    report, _ = check(instance, ChargeEvent(8, 4))
    assert report.feasible
    car, _ = report.vehicles
    assert car.minimum_kwh == 7 and car.final_kwh == 10
    assert car.stops[3].arrival_kwh == 7
    assert car.stops[3].departure_kwh == 11
    assert report.metrics.charged_kwh == pytest.approx(4)
    # [10,15) = 2.5 kWh (1 LEC + 1.5 grid), [15,18) = 1.5 kWh grid.
    assert report.metrics.energy_eur == pytest.approx(1.0)


@pytest.mark.parametrize(("event", "at", "code"), [
    (ChargeEvent(0, 1), 7, "charge_rate"),
    (ChargeEvent(1, 1), 7, "charge_rate"),
    (ChargeEvent(1, -1), 7, "charge_rate"),
    (ChargeEvent(1, 0.5, -1), 7, "charge_rate"),
    (ChargeEvent(40, 20), 7, "battery_overfill"),
    (ChargeEvent(1, 0.5), 3, "charge_location"),
    (ChargeEvent(2, 1, 1435), 7, "charge_horizon"),
])
def test_invalid_charge(tiny, event, at, code):
    assert code in check(tiny, event, at)[1]


def test_reusing_physical_station_copy_exceeds_visit_allowance(tiny):
    station = replace(tiny.stations[0], node_ids=(7, 8))
    instance = replace(tiny, stations=(station,))
    route = Route(1, tuple(Stop(i) for i in (3, 1, 2, 7, 8, 5)))
    outcome = evaluate(instance, Schedule((route, Route(2, (Stop(4), Stop(6))))))
    assert "station_visit" in {v.code for v in outcome.violations}


def test_station_visit_rejects_passengers_on_board(tiny):
    route = Route(1, tuple(Stop(i) for i in (3, 1, 7, 2, 5)))
    outcome = evaluate(tiny, Schedule((route, Route(2, (Stop(4), Stop(6))))))
    assert "passengers_at_station" in {v.code for v in outcome.violations}
