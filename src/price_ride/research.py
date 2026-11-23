"""Pilot experiment and a diagnostic fixed-route tariff exposure audit."""
from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path

import yaml

from price_ride.baselines.insertion import (construct, no_charge_counterfactual,
                                            replenishment_candidates, schedule_order)
from price_ride.data.acquire import digest, save_json
from price_ride.data.audit import pair_audit
from price_ride.domain import Schedule
from price_ride.evaluation import EPS, evaluate
from price_ride.porto.parser import load_porto_instance


def find_instance(root, stem, tariff):
    if tariff == "Flat" and stem.startswith("r") and not stem.startswith("rF"):
        stem = "rF" + stem[1:]
    if Path(stem).name != stem:
        raise ValueError("expected an instance stem")
    return load_porto_instance(root / "datasets/porto/instances" / tariff / f"{stem}.txt")


def _profile(instance):
    grid = instance.electricity.grid
    def limits(values):
        return {"min": min(values), "max": max(values), "range": max(values)-min(values)}
    output = {"grid": limits(grid), "periods": len(grid), "stations": {}}
    for station in instance.stations:
        possible = tuple(min(g, m) if s > EPS else g for g, m, s in
                         zip(grid, station.mmr, station.surplus))
        output["stations"][station.id] = {
            "mmr": limits(station.mmr), "cheapest_available_unit": limits(possible),
            "positive_surplus_periods": sum(s > EPS for s in station.surplus),
            "positive_surplus_kwh": sum(station.surplus),
            "peak_surplus_kwh_period": max(station.surplus),
            "discount_periods": [i for i, (g, p) in enumerate(zip(grid, possible)) if p < g-EPS],
        }
    return output


def _overlap(instance, report):
    grid = instance.electricity.grid
    stations = {s.id: s for s in instance.stations}
    return {"minutes_in_discounted_lec_periods": sum(
                a.end-a.start for a in report.allocations
                if stations[a.station].surplus[a.period] > EPS and
                stations[a.station].mmr[a.period] < grid[a.period]-EPS),
            "minutes_in_grid_periods_below_daily_max": sum(
                a.end-a.start for a in report.allocations if grid[a.period] < max(grid)-EPS)}


def probe_charge_options(instance, schedule, report):
    """Probe charging on fixed passenger routes, changing one vehicle at a time."""
    best_energy = None
    best_objective = None
    useful_opportunities = []
    vehicles = {v.id: v for v in instance.vehicles}
    station_nodes = {i for s in instance.stations for i in s.node_ids}
    width = instance.electricity.minutes_per_period
    boundaries = [i*width for i in range(1, len(instance.electricity.grid)+1)]
    feasible_relocations = 0
    best_same_location_energy = report.metrics.energy_eur
    for route_index, route in enumerate(schedule.routes):
        charging = [stop for stop in route.stops if stop.charge and stop.charge.kwh > EPS]
        if len(charging) != 1:
            continue
        stop, = charging
        original_start = stop.service_start + instance.node(stop.node).service
        vehicle = vehicles[route.vehicle]
        passenger_order = tuple(s.node for s in route.stops if s.node not in station_nodes)
        original_order = tuple(s.node for s in route.stops)
        same_site_starts = []
        for initial, _, _ in replenishment_candidates(instance, vehicle, passenger_order,
                                                      Counter(), float("inf")):
            charge = next(((i, s) for i, s in enumerate(initial.stops) if s.charge), None)
            if charge is None:
                continue
            index, charge_stop = charge
            ids = tuple(s.node for s in initial.stops)
            same_order = ids == original_order
            initial_start = charge_stop.service_start + instance.node(charge_stop.node).service
            event = charge_stop.charge
            times = {t for b in boundaries for t in (b, b-event.duration)
                     if initial_start + EPS < t <= instance.horizon-event.duration + EPS}
            if not same_order:
                times.add(initial_start)
            seen = set()
            for start in sorted(times):
                candidate = schedule_order(instance, vehicle, ids, event.duration, event.kwh,
                                           index, earliest_charge=start)
                if candidate is None:
                    continue
                replacement = candidate[0]
                actual = replacement.stops[index].service_start + instance.node(charge_stop.node).service
                if actual in seen:
                    continue
                seen.add(actual)
                routes = schedule.routes[:route_index] + (replacement,) + schedule.routes[route_index+1:]
                checked = evaluate(instance, Schedule(routes))
                if not checked.feasible:
                    continue
                if same_order:
                    same_site_starts.append(actual)
                    best_same_location_energy = min(best_same_location_energy, checked.metrics.energy_eur)
                else:
                    feasible_relocations += 1
                record = {"vehicle": route.vehicle, "station": charge_stop.node, "charge_start_minute": actual,
                          "same_station_and_gap": same_order, "energy_eur": checked.metrics.energy_eur,
                          "charged_kwh": checked.metrics.charged_kwh, "travel_minutes": checked.metrics.travel_minutes,
                          "objective_eur": checked.metrics.objective_eur, "overlap": _overlap(instance, checked),
                          "replacement_route": asdict(replacement)}
                if best_energy is None or record["energy_eur"] < best_energy["energy_eur"] - EPS:
                    best_energy = record
                if best_objective is None or record["objective_eur"] < best_objective["objective_eur"] - EPS:
                    best_objective = record
        useful_opportunities.append({"vehicle": route.vehicle, "station": stop.node,
                                     "original_start": original_start,
                                     "feasible_probe_count_same_station_and_gap": len(set(same_site_starts)),
                                     "last_observed_feasible_start": max(same_site_starts, default=original_start)})
    return {"method": "fixed passenger routes, station/gap alternatives and interval start/end candidates",
            "baseline_overlap": _overlap(instance, report), "tested_sessions": useful_opportunities,
            "best_same_station_and_gap_energy_eur": best_same_location_energy,
            "feasible_relocation_probes": feasible_relocations,
            "best_observed_energy_witness": best_energy, "best_observed_objective_witness": best_objective}


def execute_run(root, instance, tariff, seed, seconds):
    schedule, outcome, diagnostics = construct(instance, seed, seconds)
    name = f"{tariff}_{instance.name}_seed{seed}"
    path = root / "reports/pilot" / f"{name}.json"
    save_json(path, {"instance": instance.source, "sha256": instance.sha256,
                     "status": "feasible" if outcome.feasible else "failed",
                     "schedule": asdict(schedule), "diagnostics": diagnostics,
                     "evaluation": asdict(outcome)})
    return schedule, outcome, diagnostics, path


def _run_row(root, instance, tariff, seed, seconds):
    schedule, outcome, diagnostics, path = execute_run(root, instance, tariff, seed, seconds)
    row = {"instance": instance.name, "requests": len(instance.requests), "tariff": tariff,
           "source": instance.source, "sha256": instance.sha256, "feasible": outcome.feasible,
           "solution": path.relative_to(root / "reports").as_posix(), **diagnostics,
           "violation_counts": dict(Counter(v.code for v in outcome.violations)), "metrics": None}
    if not outcome.feasible:
        return row
    no_charge = no_charge_counterfactual(instance, schedule)
    no_charge_failures = Counter(v.code for v in no_charge.violations)
    with_charge = sum(any(s.charge and s.charge.kwh > EPS for s in r.stops) for r in schedule.routes)
    sessions = sum(s.charge is not None and s.charge.kwh > EPS for r in schedule.routes for s in r.stops)
    m = outcome.metrics
    minimum_price = min((min(instance.electricity.grid),
                         *(s.mmr[i] for s in instance.stations for i, v in enumerate(s.surplus) if v > EPS)))
    lower_bound = minimum_price*m.charged_kwh
    row.update(metrics=asdict(m), sessions=sessions, charged_routes=with_charge,
               charged_route_fraction=with_charge/len(schedule.routes),
               stations_used=len({a.station for a in outcome.allocations}),
               no_charge={"feasible": no_charge.feasible, "violations": dict(no_charge_failures),
                          "routes_below_final_reserve": len({v.vehicle for v in no_charge.violations
                                                              if v.code == "final_soc"}),
                          "vehicles": [{key: getattr(v, key) for key in ("vehicle", "minimum_kwh", "final_kwh")}
                                       for v in no_charge.vehicles]},
               battery=[{key: getattr(v, key) for key in ("vehicle", "initial_kwh", "minimum_kwh", "final_kwh")}
                        for v in outcome.vehicles],
               energy_share=m.energy_eur/m.objective_eur if m.objective_eur else 0,
               optimistic_price_only_floor_eur=lower_bound,
               optimistic_price_only_saving_ceiling_eur=max(0, m.energy_eur-lower_bound),
               timing=probe_charge_options(instance, schedule, outcome))
    return row


def charging_audit(root, config_path):
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    profiles, instances, rows = {}, {}, []
    for label in config["instances"]:
        for tariff in config["tariffs"]:
            try:
                instance = find_instance(root, label, tariff)
            except (ValueError, OSError) as exc:
                for seed in config["seeds"]:
                    rows.append({"instance": label, "requests": int(label.split("-")[-1]),
                                 "tariff": tariff, "seed": seed, "feasible": False,
                                 "source_error": str(exc), "metrics": None})
                continue
            instances[label, tariff] = instance
            profiles[tariff] = _profile(instance)
            for seed in config["seeds"]:
                rows.append(_run_row(root, instance, tariff, seed, float(config["seconds_per_run"])))
    pairs = [pair_audit(instances[label, "ToU"], instances[label, "Flat"])
             for label in config["instances"] if (label, "ToU") in instances and
             (label, "Flat") in instances]
    valid = [row for row in rows if row["feasible"]]
    threshold = config["negligible_charging_share"]
    if len(valid) != len(rows) or not valid:
        verdict = "INCONCLUSIVE"
        reason = "At least one scheduled pilot did not produce an independently verified feasible fleet."
    elif all(row["no_charge"]["feasible"] for row in valid) or all(
            row["energy_share"] <= threshold for row in valid):
        verdict = "NO-GO / NEEDS REFRAME"
        reason = "The complete pilots consistently avoided charging or the energy share met the negligible threshold."
    elif any(_cheaper_witness(row) for row in valid):
        verdict = "GO"
        reason = ("All scheduled pilots found feasible fleets that required charging on the constructed routes. "
                  "The energy share exceeded the pilot threshold. Independently checked station/gap probes "
                  "on fixed passenger routes found lower energy bills and lower effective prices per kWh.")
    else:
        verdict = "INCONCLUSIVE"
        reason = "Charging was observed, but the fixed-passenger-route probes found no cheaper checked schedules."
    result = {"config": config, "config_sha256": digest(config_path), "verdict": verdict, "reason": reason,
              "profiles": profiles, "pairs": pairs, "runs": rows, "passed": len(valid),
              "failed": len(rows)-len(valid)}
    report_dir = root / "reports"
    save_json(report_dir / "CHARGING_OPPORTUNITY_AUDIT.json", result)
    _reports(report_dir, result)
    return result


def _cheaper_witness(row):
    baseline = row["metrics"]
    witness = row["timing"]["best_observed_energy_witness"]
    return (witness is not None and witness["charged_kwh"] > EPS and
            witness["energy_eur"] < baseline["energy_eur"]-EPS and
            witness["energy_eur"]/witness["charged_kwh"] <
            baseline["energy_eur"]/baseline["charged_kwh"]-EPS)


def _reports(directory, audit):
    by_case = defaultdict(list)
    for run in audit["runs"]:
        by_case[run["requests"], run["tariff"]].append(run)
    report = ["# Charging opportunity audit", "", f"**{audit['verdict']}**. {audit['reason']}",
              "", f"{audit['passed']} feasible fleets and {audit['failed']} failed attempts. "
              "The JSON contains all runs, rejection counts, timing witnesses and source hashes.",
              "", "| Requests | Tariff | Seed | Feasible | Sessions | kWh | Energy EUR | Travel min | Excess min | Objective EUR | Energy share | No-charge feasible | Runtime s |",
              "|---:|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---|---:|"]
    pilot = ["# Baseline pilot", "",
             "Requests are processed by earliest pickup. The seed breaks request or vehicle ties. "
             "The baseline considers all ordered pair insertions into the current passenger sequences, rearranges "
             "waiting using fixed-order time/ride constraints, and uses published travel/excess coefficients for "
             "insertion ranking. It tries uncharged routes first, then one minimal replenishment stop at an "
             "empty-vehicle gap. Budget overruns, rejected candidates and uninserted request IDs are logged. "
             "Complete and incomplete schedules are replayed by the independent evaluator.", "",
             f"Seeds {audit['config']['seeds']} with a {audit['config']['seconds_per_run']} s budget per run. "
             "The deadline bounds candidate generation. Final replay and recording can finish after the deadline.",
             "", "| Requests | Tariff | Feasible / attempted | Rejected candidate checks |",
             "|---:|---|---:|---|"]
    for (requests, tariff), runs in sorted(by_case.items()):
        failures = Counter()
        for run in runs:
            failures.update(run.get("rejected_constraints", {}))
            m = run["metrics"]
            cells = (f"{run['sessions']} | {m['charged_kwh']:.3f} | {m['energy_eur']:.3f} | "
                     f"{m['travel_minutes']:.3f} | {m['excess_ride_minutes']:.3f} | "
                     f"{m['objective_eur']:.3f} | {run['energy_share']:.2%} | {run['no_charge']['feasible']}"
                     if m else " | ".join(["N/A"]*8))
            runtime = f"{run['runtime_seconds']:.3f}" if "runtime_seconds" in run else "N/A"
            report.append(f"| {requests} | {tariff} | {run['seed']} | {run['feasible']} | {cells} | {runtime} |")
        pilot.append(f"| {requests} | {tariff} | {sum(r['feasible'] for r in runs)}/{len(runs)} | "
                     + ", ".join(f"{key} {count}" for key, count in failures.items()) + " |")
    report += ["", "## Price and time exposure", "",
               "| Tariff | Grid EUR/kWh | Station | MMR EUR/kWh | Surplus periods | Cheaper LEC periods |",
               "|---|---|---:|---|---:|---:|"]
    for tariff, profile in sorted(audit["profiles"].items()):
        for sid, station in profile["stations"].items():
            report.append(f"| {tariff} | {profile['grid']['min']:.4f}–{profile['grid']['max']:.4f} | {sid} | "
                          f"{station['mmr']['min']:.4f}–{station['mmr']['max']:.4f} | "
                          f"{station['positive_surplus_periods']} | {len(station['discount_periods'])} |")
    report += ["", "Profile station IDs shown are for the largest pilot size. "
               "Prices are taken from the two pilot sizes' original files. The data audit documents "
               "price differences between the small and large ToU files.",
               "", "| Requests | Tariff | Seed | Routes charging / routes | Sites | Min / final kWh | Actual LEC discount min | Actual below-peak grid min | Fixed-route probe energy EUR | Probe LEC discount min | Optimistic price-only saving ceiling EUR |",
               "|---:|---|---:|---|---:|---|---:|---:|---:|---:|---:|"]
    for r in sorted(audit["runs"], key=lambda run: (run["requests"], run["tariff"], run["seed"])):
        if not r["feasible"]:
            continue
        t = r["timing"]
        w = t["best_observed_energy_witness"]
        r_energy = f"{w['energy_eur']:.3f}" if w else "N/A"
        r_overlap = f"{w['overlap']['minutes_in_discounted_lec_periods']:.2f}" if w else "N/A"
        report.append(f"| {r['requests']} | {r['tariff']} | {r['seed']} | {r['charged_routes']}/{len(r['battery'])} "
                      f"({r['charged_route_fraction']:.0%}) | {r['stations_used']} | "
                      f"{min(v['minimum_kwh'] for v in r['battery']):.2f} / "
                      f"{min(v['final_kwh'] for v in r['battery']):.2f} | "
                      f"{t['baseline_overlap']['minutes_in_discounted_lec_periods']:.2f} | "
                      f"{t['baseline_overlap']['minutes_in_grid_periods_below_daily_max']:.2f} | "
                      f"{r_energy} | {r_overlap} | {r['optimistic_price_only_saving_ceiling_eur']:.3f} |")
    report += ["", "The optimistic price-only ceiling prices every fixed purchased kWh at the day's "
               "lowest available unit rate. It ignores timing, station, outlet and finite surplus constraints. "
               "It is a theoretical ceiling and may be unattainable.",
               "", "Each probe independently replays the full fleet after changing one vehicle’s charging plan. "
               "Assignments and passenger order are fixed. Probes cover the existing station and gap plus other feasible "
               "empty-vehicle station/gap placements at their earliest start and at tariff-boundary starts or ends. "
               "Same-gap retiming leaves purchased kWh fixed. Relocation can change purchased kWh and road travel. "
               "Objective behavior and witness routes are available in the JSON.",
               "", "### Best checked full-objective change",
               "", "| Requests | Tariff | Seed | Baseline EUR | Best probe or baseline EUR |",
               "|---:|---|---:|---:|---:|"]
    for r in sorted(audit["runs"], key=lambda run: (run["requests"], run["tariff"], run["seed"])):
        if not r["feasible"]:
            continue
        original = r["metrics"]["objective_eur"]
        witness = r["timing"]["best_observed_objective_witness"]
        best = min(original, witness["objective_eur"]) if witness else original
        report.append(f"| {r['requests']} | {r['tariff']} | {r['seed']} | {original:.3f} | {best:.3f} |")
    report += [
               "", "## Paired tariff interpretation", ""]
    for pair in audit["pairs"]:
        report.append(f"- {pair['requests']} requests. Strict tariff-only pair **{pair['tariff_only_pair']}**. "
                      f"Maximum matrix delta {pair['matrix_max_absolute_difference_minutes']:.6f} min. "
                      "See the data audit for coordinate and time-window changes.")
    report += ["", "The verdict governs whether to continue investigating charging exposure. Published-cost "
               "comparability remains blocked by the MMR and outlet conventions in [MODEL_CONTRACT.md](MODEL_CONTRACT.md)."]
    pilot += ["", "Per-run schedules, service and battery states, charged periods and violation details are "
              "under [pilot/](pilot/). Each instance retains its own official routing matrix and time windows.",
              "See the [charging opportunity audit](CHARGING_OPPORTUNITY_AUDIT.md) for metrics."]
    (directory / "BASELINE_PILOT.md").write_text("\n".join(pilot)+"\n", encoding="utf-8")
    (directory / "CHARGING_OPPORTUNITY_AUDIT.md").write_text("\n".join(report)+"\n", encoding="utf-8")
