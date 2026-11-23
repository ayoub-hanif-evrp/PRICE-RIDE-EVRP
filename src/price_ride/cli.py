"""PRICE-RIDE acquisition, validation and pilot entry points."""
import argparse
import json
from dataclasses import asdict
from pathlib import Path

from price_ride.casablanca.network import acquire_graph, shortest_path
from price_ride.data.acquire import acquire_porto, acquire_traffic
from price_ride.data.audit import audit_data
from price_ride.domain import ChargeEvent, Route, Schedule, Stop
from price_ride.evaluation import evaluate
from price_ride.research import charging_audit, execute_run, find_instance


def parser():
    app = argparse.ArgumentParser(description=__doc__)
    app.add_argument("--root", type=Path, default=Path.cwd(), help="project data and reports root")
    commands = app.add_subparsers(dest="area", required=True)
    data = commands.add_parser("data").add_subparsers(dest="action", required=True)
    data.add_parser("download-porto")
    casablanca = data.add_parser("download-casablanca")
    casablanca.add_argument("--traffic-only", action="store_true")
    casablanca.add_argument("--osm-only", action="store_true")
    casablanca.add_argument("--fallback-url", help="author-associated URL, verified against Mendeley SHA-256")
    data.add_parser("audit")
    route = data.add_parser("casablanca-path")
    route.add_argument("origin", type=int, help="OSM node ID")
    route.add_argument("destination", type=int, help="OSM node ID")
    model = commands.add_parser("model").add_subparsers(dest="action", required=True)
    validate = model.add_parser("validate-porto")
    validate.add_argument("--schedule", type=Path, help="replay a saved pilot or schedule JSON")
    baseline = commands.add_parser("baseline").add_subparsers(dest="action", required=True)
    run = baseline.add_parser("run")
    run.add_argument("--seed", type=int, default=11)
    run.add_argument("--seconds", type=float, default=30)
    for command in (validate, run):
        command.add_argument("--instance", required=True)
        command.add_argument("--tariff", choices=["ToU", "Flat"], default="ToU")
    research = commands.add_parser("research").add_subparsers(dest="action", required=True)
    charging = research.add_parser("charging-audit")
    charging.add_argument("--config", type=Path, default=Path("configs/experiment_stage1.yaml"))
    return app


def load_schedule(path, instance_sha256):
    payload = json.loads(path.read_text(encoding="utf-8"))
    if "sha256" in payload and payload["sha256"] != instance_sha256:
        raise ValueError("saved solution is tied to a different instance SHA-256")
    rows = payload.get("schedule", payload)["routes"]
    routes = []
    for row in rows:
        stops = []
        for item in row["stops"]:
            fields = dict(item)
            if fields.get("charge") is not None:
                fields["charge"] = ChargeEvent(**fields["charge"])
            stops.append(Stop(**fields))
        routes.append(Route(row["vehicle"], tuple(stops)))
    return Schedule(tuple(routes))


def dispatch(args):
    root = args.root
    if args.action == "download-porto":
        result = acquire_porto(root)
        return {"verified": len(result["records"]), "failures": result["failures"]}, bool(result["failures"])
    if args.action == "download-casablanca":
        if args.traffic_only and args.osm_only:
            raise ValueError("choose at most one of --traffic-only and --osm-only")
        result = {}
        if not args.osm_only:
            result["traffic"] = acquire_traffic(root, args.fallback_url)
        if not args.traffic_only:
            result["osm"] = acquire_graph(root)
        return result, any(source["status"] != "verified" for source in result.values())
    if args.action == "audit":
        result = audit_data(root)
        summary = {"valid_instances": result["valid_instances"], "failures": result["validation_failures"],
                   "traffic": result["casablanca_traffic"]["status"], "osm": result["sources"]["osm"]["status"]}
        return summary, bool(summary["failures"] or summary["traffic"] != "verified" or summary["osm"] != "verified")
    if args.action == "casablanca-path":
        import networkx as nx
        import osmnx as ox
        graph = ox.load_graphml(root / "datasets/casablanca/osm/casablanca-drive.graphml")
        try:
            return shortest_path(graph, args.origin, args.destination), False
        except (nx.NetworkXNoPath, nx.NodeNotFound) as exc:
            return {"status": "unreachable", "origin": args.origin, "destination": args.destination,
                    "reason": str(exc)}, True
    if args.action == "charging-audit":
        result = charging_audit(root, root / args.config)
        return {key: result[key] for key in ("verdict", "reason", "passed", "failed")}, bool(result["failed"])
    instance = find_instance(root, args.instance, args.tariff)
    if args.action == "validate-porto":
        if args.schedule:
            report = evaluate(instance, load_schedule(args.schedule, instance.sha256))
            return asdict(report), not report.feasible
        return {"instance": instance.name, "nodes": len(instance.nodes), "requests": len(instance.requests),
                "vehicles": len(instance.vehicles), "sha256": instance.sha256, "source": instance.source,
                "valid": True}, False
    if not 0 < args.seconds < float("inf"):
        raise ValueError("--seconds must be finite and positive")
    _, report, diagnostics, path = execute_run(root, instance, args.tariff, args.seed, args.seconds)
    return {"feasible": report.feasible, "diagnostics": diagnostics, "output": str(path),
            "metrics": asdict(report.metrics) if report.feasible else None}, not report.feasible


def main():
    app = parser()
    try:
        output, failed = dispatch(app.parse_args())
    except (ValueError, OSError, KeyError, TypeError) as exc:
        app.exit(1, f"{exc}\n")
    print(json.dumps(output, indent=2, default=str, ensure_ascii=True, allow_nan=False))
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
