"""Reader for the Zenodo v4 line-oriented Porto format."""
from pathlib import Path
from math import isfinite
import hashlib

from price_ride.data.acquire import PORTO_DOI
from price_ride.domain import (ChargingStation, Instance, Node, Objective,
                               Request, TimeSeries, Vehicle)


class InstanceFormatError(ValueError):
    pass


def load_porto_instance(path):
    path = Path(path)
    raw = path.read_bytes()
    try:
        lines = raw.decode("utf-8-sig").splitlines()
    except UnicodeDecodeError as exc:
        raise InstanceFormatError(f"{path}: expected UTF-8 at byte {exc.start}") from exc
    line_number = 0

    def require(condition, explanation):
        if not condition:
            raise InstanceFormatError(f"{path}:{line_number}: {explanation}")

    def row(count, label, integral=False, nonnegative=True):
        nonlocal line_number
        line_number += 1
        require(line_number <= len(lines), f"missing {label}")
        line = lines[line_number - 1]
        try:
            values = tuple(float(token) for token in line.split())
        except ValueError:
            require(False, f"{label}: nonnumeric token")
        require(len(values) == count, f"{label}: expected {count} values, found {len(values)}")
        require(all(isfinite(v) for v in values), f"{label}: nonfinite value")
        require(not nonnegative or all(v >= 0 for v in values), f"{label}: negative value")
        if integral:
            require(all(v.is_integer() for v in values), f"{label}: integer required")
            values = tuple(int(v) for v in values)
        return values

    k, n, origin_count, end_count, s, visits, horizon = row(7, "header")
    require(all(v.is_integer() and v > 0 for v in (k, n, origin_count, end_count, s, visits))
            and horizon > 0, "invalid header")
    k, n, origin_count, end_count, s, visits = map(int, (k, n, origin_count, end_count, s, visits))
    require((origin_count, end_count, s) == (1, 1, 2), "unsupported depot/LEC profile layout")

    nodes = []

    def read_node(expected_id):
        ident, lat, lon, service, load, earliest, latest = row(7, "node", nonnegative=False)
        expected_load = 1 if expected_id <= n else -1 if expected_id <= 2*n else 0
        require(ident == expected_id and load == expected_load, "node ID or load violates node block order")
        require(-90 <= lat <= 90 and -180 <= lon <= 180, "coordinate out of WGS84 range")
        require(0 <= earliest <= latest <= horizon and 0 <= service <= horizon, "invalid node times")
        return Node(expected_id, lat, lon, service, int(load), earliest, latest)

    bare_size = 2*n + 2*k + s
    for ident in range(1, bare_size + 1):
        nodes.append(read_node(ident))
    # A station-copy row has seven columns. The single-column common origin
    # terminates the node block.
    while line_number < len(lines) and len(lines[line_number].split()) == 7:
        require(len(nodes) < bare_size + s*(visits-1), "too many station-copy nodes")
        nodes.append(read_node(len(nodes) + 1))
    common_start = row(1, "common origin", integral=True)[0]
    require(2*n < common_start <= 2*n+k, "invalid common origin")
    common_end = row(1, "common destination", integral=True)[0]
    origins = row(k, "virtual origins", integral=True)
    destinations = row(k, "virtual destinations", integral=True)
    require(set(origins) == set(range(2*n+1, 2*n+k+1)), "invalid virtual origins")
    require(set(destinations) == set(range(2*n+k+1, 2*n+2*k+1)), "invalid virtual destinations")
    require(common_start in origins and common_end in destinations, "invalid common depot references")
    station_ids = row(s, "station IDs", integral=True)
    require(set(station_ids) == set(range(2*n+2*k+1, bare_size+1)), "invalid station IDs")
    copies = {sid: [sid] for sid in station_ids}
    for node in nodes[bare_size:]:
        matches = [sid for sid in station_ids
                   if (node.latitude, node.longitude) == (nodes[sid-1].latitude, nodes[sid-1].longitude)]
        require(len(matches) == 1, f"ambiguous station copy {node.id}")
        copies[matches[0]].append(node.id)
    require({len(ids) for ids in copies.values()} == {visits}, "incomplete station-copy groups")
    rides = row(n, "ride limits")
    require(all(0 < v <= horizon for v in rides), "invalid ride limits")
    capacities = row(k, "passenger capacities", integral=True)
    require(all(capacities), "zero passenger capacity")
    initial = row(k, "initial energy")
    batteries = row(k, "battery capacity")
    ratios = row(k, "final SOC ratios")
    require(all(0 <= i <= b and b > 0 and r <= 1 for i, b, r in zip(initial, batteries, ratios)),
            "invalid battery block")
    rates = row(s, "station rates")
    require(all(rates), "zero station rate")
    consumption = row(1, "traction rate")[0]
    require(consumption > 0, "zero traction rate")
    weights = row(2, "legacy objective weights")
    travel_cost, excess_cost = row(2, "monetary coefficients")
    periods = row(1, "period count", integral=True)[0]
    require(periods == 96 and horizon == periods*15, "expected 96 15-minute periods")
    surplus = [row(periods, f"station {sid} surplus") for sid in station_ids]
    grid = row(periods, "grid tariff")
    mmr = [row(periods, f"station {sid} MMR") for sid in station_ids]
    matrix = tuple(row(len(nodes), f"matrix row {i}") for i in range(1, len(nodes) + 1))
    require(all(not content.strip() for content in lines[line_number:]), "unexpected trailing data")
    vehicles = tuple(Vehicle(i+1, *values) for i, values in enumerate(
        zip(origins, destinations, capacities, initial, batteries, ratios)))
    requests = tuple(Request(i, i, n+i, rides[i-1]) for i in range(1, n+1))
    stations = tuple(ChargingStation(sid, tuple(copies[sid]), rates[i], visits, surplus[i], mmr[i])
                     for i, sid in enumerate(station_ids))
    return Instance(path.stem, f"{PORTO_DOI}/{path.parent.name}/{path.name}",
                    hashlib.sha256(raw).hexdigest(), horizon, (origin_count, end_count),
                    (common_start, common_end), tuple(nodes), requests, vehicles, stations,
                    TimeSeries(15, grid), consumption, Objective(weights, travel_cost, excess_cost), matrix)
