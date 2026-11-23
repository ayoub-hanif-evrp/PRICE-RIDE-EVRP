"""Resumable staged development campaign. All paths and cohorts are explicit."""
import argparse
import json
import sys
from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path
from time import perf_counter
from traceback import format_exc

import yaml

from price_ride.baselines.insertion import construct
from price_ride.cli import load_schedule
from price_ride.data.acquire import digest, save_json
from price_ride.evaluation import EPS, evaluate
from price_ride.optimization.orders import passenger_orders, randomized_start
from price_ride.optimization.search import diagnostic, orders_id, run_search
from price_ride.optimization.structural import MODEL, audit
from price_ride.research import find_instance


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def save(path, value):
    if path.exists():
        raise FileExistsError(f"refusing to overwrite recorded run {path}")
    save_json(path, value)


class Campaign:
    def __init__(self, root):
        self.root = root
        self.reports = root/"reports"
        self.raw = self.reports/"stage2_v1"
        self.cfg_path = root/"configs/experiment_stage2.yaml"
        self.config = yaml.safe_load(self.cfg_path.read_text(encoding="utf-8"))
        self.config_sha = digest(self.cfg_path)
        self.rescue_path = root/"configs/experiment_stage2_construction_rescue.yaml"
        self.rescue = yaml.safe_load(self.rescue_path.read_text(encoding="utf-8"))
        self.original = {"data": read(self.reports/"DATA_AUDIT.json")}
        self.seeds = self.config["seeds"]+self.config["validation_seeds"]
        self.structure = None

    def instances(self):
        for name in self.config["development"]:
            for tariff in self.config["tariffs"]:
                item = find_instance(self.root, name, tariff)
                expected = self.original["data"]["instances"][f"{tariff}/{item.name}.txt"]["sha256"]
                if item.sha256 != expected:
                    raise ValueError(f"frozen source hash failed for {item.source}")
                yield item, tariff

    def identity(self, instance, tariff, seed):
        return {"instance": instance.name, "requests": len(instance.requests), "source": instance.source,
                "tariff": tariff, "seed": seed, "model": MODEL, "sha256": instance.sha256,
                "config_sha256": self.config_sha}

    def structural(self, include_witnesses=False):
        files = [p for p in self.raw.glob("*/starts*/*.json")
                 if read(p).get("feasible")] if include_witnesses else []
        self.structure = audit(self.root, self.original, files)
        return self.structure

    def start(self, instance, tariff, seed):
        path = self.raw/instance.name/"starts"/f"{seed}.json"
        if path.exists():
            return path, read(path)
        row = self.identity(instance, tariff, seed)
        bounded = next(r for r in self.structure["cases"] if r["instance"] == instance.name)
        if bounded["certificates"]:
            row.update(feasible=False, diagnostics={"source": "input-only infeasibility certificate"})
        else:
            historical = self.reports/"pilot"/f"{tariff}_{instance.name}_seed11.json"
            fallback = self.checked_from(instance, historical) if historical.is_file() else None
            try:
                found, info = randomized_start(instance, self.config, seed,
                                               self.config["construction_seconds"][len(instance.requests)],
                                               fallback)
                row.update(feasible=found is not None, diagnostics=info)
                if found:
                    row.update(schedule=asdict(found[0]), evaluation=asdict(found[1]),
                               orders=passenger_orders(instance, found[0]))
            except Exception:
                row.update(feasible=False, diagnostics={"source": "error", "traceback": format_exc()})
        save(path, row)
        return path, row

    def starts(self):
        self.structural()
        for instance, tariff in self.instances():
            for seed in self.seeds:
                _, row = self.start(instance, tariff, seed)
                print(instance.name, seed, row["diagnostics"]["source"], flush=True)
        self.structural(include_witnesses=True)

    def rescue_starts(self):
        for item, tariff in self.instances():
            if len(item.requests) != self.rescue["size"]:
                continue
            for seed in self.seeds:
                original_path = self.raw/item.name/"starts"/f"{seed}.json"
                original = read(original_path)
                path = self.raw/item.name/"starts_rescue"/f"{seed}.json"
                if original["feasible"] or path.exists():
                    continue
                found, info = randomized_start(item, self.config, seed, self.rescue["seconds_per_rerun"])
                row = self.identity(item, tariff, seed)
                row.update(feasible=found is not None, diagnostics=info,
                           previous_attempt=original_path.relative_to(self.root).as_posix(),
                           prior_seconds=original["diagnostics"].get("runtime_seconds", 0),
                           rescue_sha256=digest(self.rescue_path))
                if found:
                    row.update(schedule=asdict(found[0]), evaluation=asdict(found[1]),
                               orders=passenger_orders(item, found[0]))
                save(path, row)
                print("rescue", item.name, seed, row["feasible"],
                      round(info["runtime_seconds"], 3), flush=True)
        self.structural(include_witnesses=True)

    def checked_from(self, instance, path):
        schedule = load_schedule(path, instance.sha256)
        checked = evaluate(instance, schedule)
        if not checked.feasible:
            raise ValueError(f"saved incumbent failed independent replay: {path}")
        return schedule, checked

    def load_start(self, item, seed):
        path = self.raw/item.name/"starts"/f"{seed}.json"
        row = read(path)
        rescue = self.raw/item.name/"starts_rescue"/f"{seed}.json"
        if not row["feasible"] and rescue.is_file():
            path, row = rescue, read(rescue)
            if row["rescue_sha256"] != digest(self.rescue_path):
                raise ValueError(f"incompatible rescue protocol {path}")
        if row["sha256"] != item.sha256 or row["model"] != MODEL or row["config_sha256"] != self.config_sha:
            raise ValueError(f"incompatible shared start {path}")
        runtime = float(row["diagnostics"].get("runtime_seconds", 0)+row.get("prior_seconds", 0))
        return row, path, runtime

    def diagnostics(self):
        snapshot = self.raw/"comparison_freeze.json"
        if not snapshot.exists():
            paths = sorted((self.root/"src/price_ride/optimization").glob("*.py"))
            paths += [self.root/"src/price_ride/evaluation.py", self.cfg_path, self.rescue_path,
                      self.reports/"STAGE2_PROTOCOL.md", self.reports/"MODEL_CONTRACT_V2.md",
                      self.reports/"PRICE_RIDE_METHOD.md"]
            save(snapshot, {"design": "stage2_v1", "model": MODEL, "config_sha256": self.config_sha,
                            "files": {p.relative_to(self.root).as_posix(): digest(p) for p in paths}})
        for item, tariff in self.instances():
            for seed in self.config["seeds"]:
                path = self.raw/item.name/"diagnostics"/f"{seed}.json"
                if path.exists():
                    continue
                start, start_path, _ = self.load_start(item, seed)
                row = self.identity(item, tariff, seed)
                row["shared_start"] = start_path.relative_to(self.root).as_posix()
                if not start["feasible"]:
                    row.update(status="unresolved_start", diagnostic=None)
                else:
                    try:
                        row.update(status="complete", diagnostic=diagnostic(
                            item, self.config, seed, self.checked_from(item, start_path)))
                    except Exception:
                        row.update(status="error", diagnostic=None, traceback=format_exc())
                save(path, row)
                print("diagnostic", item.name, seed, row["status"], flush=True)
        self.summarize_diagnostics()

    def runs(self):
        expected = len(self.config["development"])*len(self.config["tariffs"])*len(self.config["seeds"])
        snapshot = read(self.raw/"comparison_freeze.json")
        if snapshot["config_sha256"] != self.config_sha or any(
                digest(self.root/p) != sha for p, sha in snapshot["files"].items()):
            raise ValueError("comparison inputs or implementation changed after diagnostic freeze")
        if len(list(self.raw.glob("*/diagnostics/*.json"))) != expected:
            raise ValueError("complete the diagnostic stage before running the comparison")
        structure = read(self.reports/"STRUCTURAL_FEASIBILITY_AUDIT.json")
        cases = {r["instance"]: r for r in structure["cases"]}
        for item, tariff in self.instances():
            for seed in self.seeds:
                split = "development" if seed in self.config["seeds"] else "validation_seed"
                methods = self.config["methods"] if split == "development" else self.config["validation_methods"]
                for method in methods:
                    path = self.raw/item.name/"runs"/f"{seed}_{method}.json"
                    if path.exists():
                        continue
                    row = self._run(item, tariff, seed, method, split, cases[item.name])
                    save(path, row)
                    print(item.name, seed, method, row["status"],
                          round(row["runtime_seconds"], 3),
                          round(row["metrics"]["objective_eur"], 6) if row["metrics"] else "—",
                          flush=True)
        self.summarize_runs()

    def _run(self, item, tariff, seed, method, split, structural):
        start_time = perf_counter()
        seconds = self.config["seconds"][len(item.requests)]
        row = self.identity(item, tariff, seed)
        row.update(method=method, split=split, budget_seconds=seconds, feasible=False, metrics=None)
        start, start_path, startup = self.load_start(item, seed)
        try:
            if structural["certificates"]:
                row.update(status="certified_infeasible", runtime_seconds=0.0)
                return row
            if method == "B0":
                schedule, report, info = construct(item, seed, seconds)
                startup = 0
            else:
                row.update(shared_start=start_path.relative_to(self.root).as_posix(),
                           construction_seconds=startup)
                if not start["feasible"]:
                    row.update(status="unresolved_start", runtime_seconds=startup,
                               start_diagnostics=start["diagnostics"])
                    return row
                initial = self.checked_from(item, start_path)
                row.update(initial_order_id=orders_id(passenger_orders(item, initial[0])),
                           initial_objective_eur=initial[1].metrics.objective_eur)
                (schedule, report), info = run_search(item, self.config, seed, method, initial,
                                                       seconds-startup-(perf_counter()-start_time))
            # The saved monetary values always come from the independent evaluator.
            report = evaluate(item, schedule)
            elapsed = perf_counter()-start_time+startup
            row.update(status="feasible" if report.feasible else "incomplete",
                       feasible=report.feasible, metrics=asdict(report.metrics) if report.feasible else None,
                       runtime_seconds=elapsed, overrun_seconds=max(0.0, elapsed-seconds),
                       timeout=bool(info.get("budget_exhausted", info.get("budget_hit"))),
                       search=info, schedule=asdict(schedule), evaluation=asdict(report))
            row.update(kpis=self.kpis(item, schedule, report))
        except Exception:
            row.update(status="error", runtime_seconds=perf_counter()-start_time, traceback=format_exc())
        return row

    @staticmethod
    def kpis(instance, schedule, report):
        event_count = sum(s.charge is not None and s.charge.kwh > EPS for r in schedule.routes for s in r.stops)
        m = report.metrics
        return {"served_requests": len({r.request for r in report.rides}),
                "violations": dict(Counter(x.code for x in report.violations)),
                "effective_eur_per_kwh": m.energy_eur/m.charged_kwh if m.charged_kwh and report.feasible else None,
                "charging_sessions": event_count, "stations_used": sorted({a.station for a in report.allocations}),
                "active_vehicles": sum(sum(instance.travel(a.node,b.node) for a,b in zip(r.stops,r.stops[1:]))
                                       > EPS for r in schedule.routes),
                "soc": [{"vehicle": v.vehicle, "min": v.minimum_kwh, "final": v.final_kwh} for v in report.vehicles]}

    def summarize_diagnostics(self):
        paths = sorted(self.raw.glob("*/diagnostics/*.json"))
        detail = []
        for path in paths:
            row = read(path)
            raw = row.pop("diagnostic")
            row["path"] = path.relative_to(self.root).as_posix()
            if raw:
                batches = raw["batches"]
                records = [p for b in batches for p in b["evaluated"] if p["delta"] is not None]
                row.update(seconds=raw["seconds"], counts=raw["counts"], fixed_order_delta=raw["fixed_order_delta"],
                           batches=len(batches), proposals=sum(b["proposals"] for b in batches),
                           ranked=sum(b["ranked"] for b in batches),
                           overlap=sum(b["overlap"] for b in batches),
                           compared=sum(b["blind_best"] is not None and b["guided_best"] is not None
                                        for b in batches),
                           ranked_differently=sum(b["blind_ids"] != b["guided_ids"] for b in batches),
                           guided_better=sum(b["blind_best"] is not None and b["guided_best"] is not None
                                             and b["guided_best"] < b["blind_best"]-EPS for b in batches),
                           neutral_better=sum(b["blind_best"] is not None and b["guided_best"] is not None
                                              and b["blind_best"] < b["guided_best"]-EPS for b in batches),
                           checked_feasible=len(records), evaluated=sum(len(b["evaluated"]) for b in batches),
                           net_improving=sum(p["delta"]["objective_eur"] < -EPS for p in records),
                           lower_energy=sum(p["delta"]["energy_eur"] < -EPS for p in records),
                           best_net_delta=min((p["delta"]["objective_eur"] for p in records), default=None))
            detail.append(row)
        result = {"model": MODEL, "rows": detail}
        save_json(self.reports/"JOINT_OPPORTUNITY_AUDIT.json", result)
        lines = ["# Joint opportunity diagnostic", "",
                 "All moves start from a common complete schedule after fixed-order charging. "
                 "Each batch replays the union of predeclared neutral and guided shortlists. "
                 "Deltas below use the full EUR objective. Data are kept by official filename.",
                 "", "| Instance | Completed / planned | Ranked differently | Guided / neutral wins | Evaluated / feasible | Net improving | Energy-lowering | Best delta EUR |",
                 "|---|---:|---:|---:|---:|---:|---:|---:|"]
        for name in sorted({r["instance"] for r in detail}):
            rows = [r for r in detail if r["instance"] == name]
            def total(k):
                return sum(r.get(k, 0) for r in rows)
            best = min((r["best_net_delta"] for r in rows if r.get("best_net_delta") is not None), default=None)
            best_string = f"{best:+.3f}" if best is not None else "—"
            lines.append(f"| {name} | {sum(r['status']=='complete' for r in rows)}/{len(rows)} | "
                         f"{total('ranked_differently')}/{total('batches')} | {total('guided_better')}/{total('neutral_better')} | "
                         f"{total('evaluated')}/{total('checked_feasible')} | {total('net_improving')} | "
                         f"{total('lower_energy')} | {best_string} |")
        lines += ["", "Machine rows include total shortlist overlap, price-aware and neutral wins, and the fixed-order "
                  "charging control delta for every seed. Raw batches contain each move's travel/user/energy components."]
        (self.reports/"JOINT_OPPORTUNITY_AUDIT.md").write_text("\n".join(lines)+"\n", encoding="utf-8")

    def summarize_runs(self):
        from price_ride.optimization.reporting import development_summary
        paths = sorted(self.raw.glob("*/runs/*.json"))
        rows = []
        for path in paths:
            row = read(path)
            info = row.pop("search", {})
            trace = info.pop("trace", [])
            row.pop("schedule", None)
            row.pop("evaluation", None)
            row["search_counts"] = info
            row["path"] = path.relative_to(self.root).as_posix()
            row["evaluated_moves"] = sum(len(t.get("evaluated", [])) for t in trace)
            row["choice_changes"] = sum(t.get("shortlist_changed", False) for t in trace)
            row["first_choice_changes"] = sum(t.get("first_changed", False) for t in trace)
            row["accepted_moves"] = [t["accepted"] for t in trace if t.get("accepted")]
            rows.append(row)
        development_summary(self.reports, self.config, rows, self.config_sha)

    def replay(self):
        records = []
        cache = {item.name: item for item, _ in self.instances()}
        for path in sorted([*self.raw.glob("*/runs/*.json"), *self.raw.glob("*/starts*/*.json")]):
            row = read(path)
            item = cache[row["instance"]]
            entry = {"path": path.relative_to(self.root).as_posix(), "declared_feasible": row["feasible"]}
            if row["sha256"] != item.sha256 or row["model"] != MODEL or row["config_sha256"] != self.config_sha:
                entry.update(status="failed", reason="source, model or config identity")
            elif "schedule" not in row:
                entry.update(status="failed" if row["feasible"] else "no saved schedule")
            else:
                score = evaluate(item, load_schedule(path, item.sha256))
                outcome_matches = score.feasible == row["feasible"]
                metrics_match = all(abs(value-row["evaluation"]["metrics"][name]) <= EPS
                                    for name, value in asdict(score.metrics).items())
                entry.update(status="verified" if outcome_matches and metrics_match else "failed",
                             replay_feasible=score.feasible, metrics_match=metrics_match)
            records.append(entry)
        result = {"model": MODEL, "counts": dict(Counter(r["status"] for r in records)), "records": records}
        save_json(self.raw/"replay.json", result)
        return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["structural", "starts", "rescue-starts", "diagnostics",
                                           "compare", "replay", "summarize"])
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    campaign = Campaign(args.root.resolve())
    if args.action == "structural":
        result = campaign.structural(include_witnesses=True)
        print(dict(Counter(row["status"] for row in result["cases"])))
    elif args.action == "starts":
        campaign.starts()
    elif args.action == "rescue-starts":
        campaign.rescue_starts()
    elif args.action == "diagnostics":
        campaign.diagnostics()
    elif args.action == "compare":
        campaign.runs()
    elif args.action == "replay":
        result = campaign.replay()
        print(result["counts"])
        return int(result["counts"].get("failed", 0) > 0)
    else:
        campaign.summarize_diagnostics()
        campaign.summarize_runs()
    return 0


if __name__ == "__main__":
    sys.exit(main())
