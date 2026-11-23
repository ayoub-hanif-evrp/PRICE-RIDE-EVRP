from pathlib import Path
from zipfile import ZipFile

import pytest

from price_ride.data.acquire import EXPECTED, PORTO_FILES, checked_members, digest
from price_ride.porto.parser import InstanceFormatError, load_porto_instance

ROOT = Path(__file__).resolve().parents[1]


def fixture_text(tiny, copies=False):
    stamp = "2 1 1 1 2 " + ("2" if copies else "1") + " 1440"
    nodes = list(tiny.nodes)
    rows = [[n.id, n.latitude, n.longitude, n.service, n.load, n.earliest, n.latest] for n in nodes]
    indices = list(range(8))
    if copies:
        for i in (6, 7):
            rows.append([len(rows)+1, *rows[i][1:]])
            indices.append(i)
    common = [[3], [5], [3, 4], [5, 6], [7, 8], [60], [4, 4],
              [10, 10], [15, 15], [.4, .4], [.5, .5], [.5], [.75, .25], [.36, .31], [96]]
    profiles = [s.surplus for s in tiny.stations] + [tiny.electricity.grid] + [s.mmr for s in tiny.stations]
    matrix = [[tiny.matrix[i][j] for j in indices] for i in indices]
    return [stamp, *(" ".join(map(str, r)) for r in [*rows, *common, *profiles, *matrix])]


def test_parse_fixture_and_station_copies(tmp_path, tiny):
    path = tmp_path / "r2-1.txt"
    path.write_text("\n".join(fixture_text(tiny, copies=True)))
    instance = load_porto_instance(path)
    assert len(instance.nodes) == len(instance.matrix[0]) == 10
    assert instance.requests == tiny.requests
    assert instance.vehicles == tiny.vehicles
    assert [s.node_ids for s in instance.stations] == [(7, 9), (8, 10)]
    assert instance.travel(1, 9) == tiny.travel(1, 7)
    assert instance.sha256 == digest(path)


@pytest.mark.parametrize(("index", "change", "message"), [
    (1, "1 100 0 0 1 0 1440", "coordinate"),
    (2, "2 40 0 0 1 0 1440", "node ID or load"),
    (25, "0", "expected 96"),
    (-1, "nan 0 0 0 0 0 0 0", "nonfinite"),
    (-1, "0 0 0 0 0 0 0 -1", "negative"),
    (-1, "0 0", "expected 8"),
])
def test_bad_file(tmp_path, tiny, index, change, message):
    path = tmp_path / "bad.txt"
    rows = fixture_text(tiny)
    rows[index] = change
    path.write_text("\n".join(rows))
    line = index+1 if index >= 0 else len(rows)+index+1
    with pytest.raises(InstanceFormatError, match=rf":{line}: .*{message}"):
        load_porto_instance(path)


def test_archive_path_traversal(tmp_path):
    path = tmp_path / "unsafe.zip"
    with ZipFile(path, "w") as archive:
        archive.writestr("../escape.txt", b"invalid archive member")
    with ZipFile(path) as archive, pytest.raises(ValueError, match="unsafe"):
        checked_members(archive)


@pytest.mark.official
def test_all_official_files():
    root = ROOT / "datasets/porto"
    source = root / "raw/Instances.zip"
    if not source.is_file():
        pytest.skip("run data download-porto for the official integration test")
    assert digest(source, "md5") == PORTO_FILES[source.name]
    paths = set(path.relative_to(root / "instances") for path in (root / "instances").glob("*/*.txt"))
    assert paths == EXPECTED
    with ZipFile(source) as zipfile:
        for relative in sorted(paths):
            path = root / "instances" / relative
            item = load_porto_instance(path)
            assert path.read_bytes() == zipfile.read("Instances/" + relative.as_posix())
            assert len(item.electricity.grid) == 96
            assert len(item.matrix) == len(item.nodes)
