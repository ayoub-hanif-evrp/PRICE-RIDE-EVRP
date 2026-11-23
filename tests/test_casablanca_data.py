from pathlib import Path

import networkx as nx
import pytest

from price_ride.casablanca.network import check_graph, shortest_path
from price_ride.casablanca.traffic import load_observations, positive, summarize
from price_ride.data.acquire import TRAFFIC_NAME, TRAFFIC_SHA, digest

ROOT = Path(__file__).resolve().parents[1]


def test_tti_summary_preserves_variance_and_median():
    numbers = [1, 2, 3, 4]
    result = summarize(numbers)
    assert result["mean"] == result["median"] == 2.5
    assert result["variance"] == 1.25
    assert positive("1") is None and positive(0) is None
    assert summarize([]) == {"count": 0}


def test_directed_shortest_path_keeps_one_way_and_parallel_edges():
    graph = nx.MultiDiGraph()
    graph.add_edge(10, 20, length=5)
    graph.add_edge(10, 20, length=2)
    graph.add_edge(20, 30, length=3)
    assert shortest_path(graph, 10, 30)["length_m"] == 5
    with pytest.raises(nx.NetworkXNoPath):
        shortest_path(graph, 30, 10)


@pytest.mark.official
def test_original_traffic_workbook():
    path = ROOT / "datasets/casablanca/raw" / TRAFFIC_NAME
    if not path.is_file():
        pytest.skip("run data download-casablanca --traffic-only")
    assert digest(path) == TRAFFIC_SHA
    layouts, entries = load_observations(path)
    assert len(layouts) == 13
    assert len(entries) == 440*24*7
    assert entries[0]["travel_time_raw"] == 12.583
    assert entries[0]["origin_lat"] == pytest.approx(33.5696864)
    assert entries[0]["tti"] == pytest.approx(1.2641484)


@pytest.mark.official
def test_frozen_osm_graph():
    import json
    import osmnx as ox
    base = ROOT / "datasets/casablanca/osm"
    path = base / "casablanca-drive.graphml"
    if not path.is_file():
        pytest.skip("run data download-casablanca --osm-only")
    metadata = json.loads((base / "provenance.json").read_text(encoding="utf-8"))
    assert digest(path) == metadata["sha256"]
    quality = check_graph(ox.load_graphml(path))
    assert quality == {key: metadata[key] for key in quality}
