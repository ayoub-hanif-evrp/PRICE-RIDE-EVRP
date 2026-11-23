# Baseline pilot

Requests are processed by earliest pickup. The seed breaks request or vehicle ties. The baseline considers all ordered pair insertions into the current passenger sequences, rearranges waiting using fixed-order time/ride constraints, and uses published travel/excess coefficients for insertion ranking. It tries uncharged routes first, then one minimal replenishment stop at an empty-vehicle gap. Budget overruns, rejected candidates and uninserted request IDs are logged. Complete and incomplete schedules are replayed by the independent evaluator.

Seeds [11, 29, 47] with a 30 s budget per run. The deadline bounds candidate generation. Final replay and recording can finish after the deadline.

| Requests | Tariff | Feasible / attempted | Rejected candidate checks |
|---:|---|---:|---|
| 20 | Flat | 3/3 | time_window_or_ride 16503, fleet_station_visits 114, charging_time_window_or_ride 801, single_charge_energy 54 |
| 20 | ToU | 3/3 | time_window_or_ride 16503, fleet_station_visits 114, charging_time_window_or_ride 801, single_charge_energy 54 |
| 40 | Flat | 3/3 | time_window_or_ride 73602, charging_time_window_or_ride 7017, fleet_station_visits 2832, single_charge_energy 1020, no_single_charge_insertion 3 |
| 40 | ToU | 3/3 | time_window_or_ride 73602, charging_time_window_or_ride 7023, fleet_station_visits 2832, single_charge_energy 1014, no_single_charge_insertion 3 |

Per-run schedules, service and battery states, charged periods and violation details are under [pilot/](pilot/). Each instance retains its own official routing matrix and time windows.
See the [charging opportunity audit](CHARGING_OPPORTUNITY_AUDIT.md) for metrics.
