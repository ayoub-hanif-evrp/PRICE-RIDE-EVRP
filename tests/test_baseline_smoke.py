from dataclasses import replace

from price_ride.baselines.insertion import construct, no_charge_counterfactual


def test_construct_and_counterfactual(tiny):
    instance = replace(tiny, vehicles=tuple(replace(v, final_ratio=2/3) for v in tiny.vehicles))
    schedule, result, diagnostic = construct(instance, seed=11, seconds=3)
    assert result.feasible
    assert len(result.rides) == 1
    assert diagnostic["uninserted_request_ids"] == []
    assert result.metrics.charged_kwh == 4
    counterfactual = no_charge_counterfactual(instance, schedule)
    assert not counterfactual.feasible
    assert {v.code for v in counterfactual.violations} == {"final_soc"}
    assert construct(instance, seed=11, seconds=3)[0] == schedule
