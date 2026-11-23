"""Freeze and query the directed OSM driving graph within Casablanca city."""
import math
import time
from pathlib import Path

from price_ride.data.acquire import digest, now, save_json

PLACE = "Casablanca, Morocco"
CITY = "R4072985"
NOMINATIM = "https://nominatim.openstreetmap.org"
OVERPASS = ("https://overpass-api.de/api", "https://overpass.kumi.systems/api")


def shortest_path(graph, origin, destination):
    import networkx as nx
    nodes = nx.shortest_path(graph, origin, destination, weight="length")
    distance = math.fsum(min(edge["length"] for edge in graph[u][v].values())
                         for u, v in zip(nodes, nodes[1:]))
    return {"origin": origin, "destination": destination, "nodes": nodes, "length_m": distance}


def check_graph(graph):
    import networkx as nx
    if not graph.is_directed() or not graph.number_of_edges():
        raise ValueError("expected a nonempty directed driving graph")
    weak = sorted(nx.weakly_connected_components(graph), key=lambda c: (-len(c), min(c)))
    strong = sorted(nx.strongly_connected_components(graph), key=lambda c: (-len(c), min(c)))
    lengths = [edge["length"] for _, _, edge in graph.edges(data=True)]
    if not all(math.isfinite(v) and v >= 0 for v in lengths) or len(strong[0]) < 3:
        raise ValueError("invalid edge lengths or inadequate directed connectivity")
    core = sorted(strong[0])
    selected = (core[0], core[len(core)//2], core[-1])
    x = [data["x"] for _, data in graph.nodes(data=True)]
    y = [data["y"] for _, data in graph.nodes(data=True)]
    return {"nodes": len(graph), "edges": len(lengths), "directed": graph.is_directed(),
            "weak_components": len(weak), "strong_components": len(strong),
            "largest_weak_nodes": len(weak[0]), "largest_strong_nodes": len(strong[0]),
            "length_m": {"min": min(lengths), "max": max(lengths), "sum": math.fsum(lengths)},
            "extent_wsen": [min(x), min(y), max(x), max(y)],
            "sample_paths": [shortest_path(graph, a, b)
                             for a, b in zip(selected, selected[1:] + selected[:1])]}


def acquire_graph(root: Path):
    import json
    import networkx as nx
    import osmnx as ox

    target = root / "datasets/casablanca/osm"
    target.mkdir(parents=True, exist_ok=True)
    graph_path = target / "casablanca-drive.graphml"
    metadata_path = target / "provenance.json"
    if graph_path.exists() and metadata_path.exists():
        record = json.loads(metadata_path.read_text(encoding="utf-8"))
        if record.get("sha256") == digest(graph_path):
            quality = check_graph(ox.load_graphml(graph_path))
            if any(record.get(key) != value for key, value in quality.items()):
                record.update(quality)
                save_json(metadata_path, record)
            return record

    ox.settings.cache_folder = target / "http-cache"
    ox.settings.http_user_agent = "PRICE-RIDE academic OSM extraction"
    ox.settings.nominatim_url = NOMINATIM
    ox.settings.requests_timeout = 60
    ox.settings.overpass_rate_limit = False  # HTTPS endpoint probes are bounded and sequential
    result = {"place_query": PLACE, "osm_relation": CITY, "status": "BLOCKED",
              "license": "ODbL 1.0", "attribution": "© OpenStreetMap contributors",
              "copyright_url": "https://www.openstreetmap.org/copyright",
              "osmnx": ox.__version__, "networkx": nx.__version__, "failures": []}
    for index, endpoint in enumerate(OVERPASS):
        ox.settings.overpass_url = endpoint
        phase = "Nominatim boundary lookup"
        try:
            boundary = ox.geocode_to_gdf(CITY, by_osmid=True)
            row = boundary.iloc[0]
            west, south, east, north = boundary.total_bounds
            if (int(row.osm_id) != 4072985 or row.osm_type != "relation" or
                    row.get("addresstype") != "city" or "Casablanca" not in row.display_name or
                    not (-7.9 < west < east < -7.3 and 33.3 < south < north < 33.8)):
                raise ValueError(f"unexpected boundary: {row.display_name}, {boundary.total_bounds}")
            boundary.to_file(target / "boundary.geojson", driver="GeoJSON", index=False)
            result.update(boundary_name=row.display_name, boundary_extent_wsen=list(boundary.total_bounds),
                          boundary_sha256=digest(target / "boundary.geojson"))
            phase = "Overpass driving graph"
            graph = ox.graph_from_polygon(row.geometry, network_type="drive", retain_all=True)
            check_graph(graph)
            temporary = target / "casablanca-drive.tmp.graphml"
            ox.save_graphml(graph, temporary)
            quality = check_graph(ox.load_graphml(temporary))
            temporary.replace(graph_path)
            result.update(quality, status="verified", endpoint=endpoint, retrieved_utc=now(),
                          sha256=digest(graph_path), bytes=graph_path.stat().st_size,
                          components="All weak components retained. Sample paths use the largest strong component.")
            break
        except Exception as exc:
            result["failures"].append({"phase": phase, "nominatim": NOMINATIM,
                                       "overpass": endpoint, "error": str(exc), "utc": now()})
            save_json(metadata_path, result)
            if index + 1 < len(OVERPASS):
                time.sleep(2)
    save_json(metadata_path, result)
    return result
