"""Development comparison and decision calculations."""
from collections import Counter, defaultdict
from statistics import mean, median

from price_ride.data.acquire import save_json
from price_ride.evaluation import EPS
from price_ride.optimization.structural import MODEL


def estimate(values):
    if not values:
        return {"count": 0, "mean": None, "median": None, "min": None, "max": None}
    return {"count": len(values), "mean": mean(values), "median": median(values),
            "min": min(values), "max": max(values)}


def development_summary(directory, cfg, rows, config_sha):
    by_case = defaultdict(list)
    for row in rows:
        by_case[row["instance"], row["method"]].append(row)
    methods = []
    for (case, method), group in sorted(by_case.items(), key=lambda item: (
            item[1][0]["requests"], *item[0])):
        dev = [r for r in group if r["split"] == "development"]
        ok = [r for r in dev if r["feasible"]]
        methods.append({"instance": case, "requests": group[0]["requests"], "method": method,
                        "attempted": len(dev), "feasible": len(ok),
                        "status": dict(Counter(r["status"] for r in dev)),
                        "objective_eur": estimate([r["metrics"]["objective_eur"] for r in ok]),
                        "energy_eur": estimate([r["metrics"]["energy_eur"] for r in ok]),
                        "runtime_seconds": estimate([r["runtime_seconds"] for r in dev]),
                        "evaluated_moves": sum(r["evaluated_moves"] for r in dev),
                        "choice_changes": sum(r["choice_changes"] for r in dev),
                        "guided_only_accepts": sum(m["guided_only"] for r in dev for m in r["accepted_moves"]),
                        "guided_only_improving_accepts": sum(m["guided_only"] and m["delta"]["objective_eur"] < -EPS
                                                             for r in dev for m in r["accepted_moves"]),
                        "timeout_counts": sum(r.get("timeout", False) for r in dev),
                        "max_overrun_seconds": max((r.get("overrun_seconds", 0) for r in dev), default=0)})
    pairs, generic = [], []
    cases = defaultdict(dict)
    for row in rows:
        cases[row["instance"], row["seed"], row["split"]][row["method"]] = row
    for (name, seed, split), pair in sorted(cases.items()):
        for baseline, candidate, out in (("B3", "P", pairs), ("B1", "B3", generic)):
            if baseline not in pair or candidate not in pair:
                continue
            a, b = pair[baseline], pair[candidate]
            joint = a["feasible"] and b["feasible"]
            same = a.get("initial_order_id") == b.get("initial_order_id")
            ratio = None
            difference = None
            if joint and same:
                difference = {k: b["metrics"][k]-a["metrics"][k]
                              for k in ("travel_eur", "user_eur", "energy_eur", "objective_eur",
                                        "travel_minutes", "excess_ride_minutes")}
                if a["metrics"]["objective_eur"] > EPS:
                    ratio = -100*difference["objective_eur"]/a["metrics"]["objective_eur"]
            out.append({"instance": name, "seed": seed, "split": split, "same_start": same,
                        "baseline_status": a["status"], "candidate_status": b["status"],
                        "gain_pct": ratio, "candidate_minus_baseline": difference,
                        "candidate_minus_baseline_evaluated": b["evaluated_moves"]-a["evaluated_moves"]})
    configurations = {}
    for split in ("development", "validation_seed"):
        configurations[split] = {}
        for name in sorted({p["instance"] for p in pairs}):
            subset = [p for p in pairs if p["split"] == split and p["instance"] == name]
            values = [p["gain_pct"] for p in subset if p["gain_pct"] is not None]
            configurations[split][name] = {**estimate(values), "planned": len(subset)}
    dev_values = [p["gain_pct"] for p in pairs if p["split"] == "development" and p["gain_pct"] is not None]
    validation_values = [p["gain_pct"] for p in pairs if p["split"] == "validation_seed" and p["gain_pct"] is not None]
    effects = {k: v["median"] for k, v in configurations["development"].items() if v["median"] is not None}
    reps = estimate(list(effects.values()))
    positive = sum(value > EPS for value in effects.values())
    lost = sum(p["baseline_status"] == "feasible" and p["candidate_status"] != "feasible" for p in pairs)
    meaningful = sum(r["guided_only_improving_accepts"] for r in methods if r["method"] == "P")
    gates = {
        "joint_threshold": bool(dev_values) and median(dev_values) >= cfg["predeclared_median_gain_pct"],
        "positive_configurations": (bool(effects) and positive/len(effects) >= cfg["positive_config_fraction"]),
        "paired_feasibility": lost == 0 and bool(dev_values),
        "guided_accepts": meaningful > 0,
        "original_cohort": len(effects) >= cfg["min_original_configs"],
        "larger_feasible_dev": any(row["requests"] >= 80 and row["feasible"] for row in rows),
    }
    if all(gates.values()):
        decision = "CONDITIONAL"
        reason = "The numeric gates passed. Author clarification and an independently credible larger cohort remain open."
    elif (gates["joint_threshold"] or gates["positive_configurations"]) and meaningful:
        decision = "CONDITIONAL"
        reason = "The guided operator changed decisions and helped in some cases. The full development gate did not pass."
    else:
        decision = "NO-GO"
        reason = "The development comparison did not establish practically meaningful superiority over the matched B3 control."
    summary = {"model": MODEL, "config_sha256": config_sha, "verdict": decision, "reason": reason,
               "gates": gates, "methods": methods, "by_configuration": configurations,
               "positive_configurations": positive, "common_configuration_count": len(effects),
               "common_feasible_development_pct": estimate(dev_values),
               "common_feasible_validation_pct": estimate(validation_values),
               "instance_level_gain_pct": reps, "candidate_feasibility_losses": lost,
               "guided_only_improving_accepts": meaningful,
               "leave_one_configuration_out_median_pct": {
                   k: median(v for other, v in effects.items() if k != other)
                   for k in effects if len(effects) > 1},
               "B3_to_P_signed_pairs": pairs, "B1_to_B3_signed_pairs": generic, "runs": rows}
    save_json(directory/"STAGE2_DEVELOPMENT_RESULTS.json", summary)
    write_summary(directory, summary)


def write_summary(directory, result):
    def fmt(value, decimals=3):
        return f"{value:.{decimals}f}" if value is not None else "—"
    lines = ["# Stage 2 original-data development results", "",
             f"**{result['verdict']}**. {result['reason']}", "",
             "Common-feasible comparisons use the same source file, seed and start. "
             "Positive signed percentage represents lower cost for P. The run-level median is "
             f"**{fmt(result['common_feasible_development_pct']['median'])}%** "
             f"over {result['common_feasible_development_pct']['count']} paired development runs. "
             f"{result['positive_configurations']} of {result['common_configuration_count']} configurations "
             "have positive median direction. Validation seeds are displayed separately. An em dash marks "
             "unavailable values.", "",
             "| Instance | Method | Feasible / planned | Mean objective EUR | Mean energy EUR | Mean runtime s | Actual move trials |",
             "|---|---|---:|---:|---:|---:|---:|"]
    for row in result["methods"]:
        lines.append(f"| {row['instance']} | {row['method']} | {row['feasible']}/{row['attempted']} | "
                     f"{fmt(row['objective_eur']['mean'])} | {fmt(row['energy_eur']['mean'])} | "
                     f"{fmt(row['runtime_seconds']['mean'])} | {row['evaluated_moves']} |")
    lines += ["", "| Instance | Paired development / planned | Median gain % | Mean % | Min / max % | Seed validation median % |",
              "|---|---:|---:|---:|---:|---:|"]
    for name, group in result["by_configuration"]["development"].items():
        valid = result["by_configuration"]["validation_seed"][name]
        lines.append(f"| {name} | {group['count']}/{group['planned']} | {fmt(group['median'])} | "
                     f"{fmt(group['mean'])} | {fmt(group['min'])} / {fmt(group['max'])} | {fmt(valid['median'])} |")
    lines += ["", f"Candidate-only improving accepts {result['guided_only_improving_accepts']}. "
              f"Paired feasibility losses {result['candidate_feasibility_losses']}. "
              "The JSON preserves component deltas, every failed or unstarted row, and leave-one-configuration-out "
              "medians. Repeated seeds are within-case observations. There is no inference to held-out cases.",
              "", "| Decision gate | Result |", "|---|---|"]
    lines += [f"| {g} | {'PASS' if value else 'FAIL'} |" for g, value in result["gates"].items()]
    (directory/"STAGE2_DEVELOPMENT_RESULTS.md").write_text("\n".join(lines)+"\n", encoding="utf-8")
