"""Verify and freeze original public research sources."""
import hashlib
import json
import os
import shutil
import stat
import time
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from urllib.request import Request, urlopen
from zipfile import ZipFile

PORTO = "https://zenodo.org/records/20707207"
PORTO_DOI = "10.5281/zenodo.20707207"
PORTO_FILES = {
    "Instances.zip": "4a11e54d90cd3a2bb32259739c5ce6bf",
    "README_v2.txt": "418d05c225f20b9cea284a04feb42da6",
    "results_LEC.zip": "4d083f0fe431326dbf74c49a24de3f4f",
    "LEC_results_midPoint.xlsx": "54deb508ed85dd1f37634e47a0653eb3",
    "generate_instances.jl": "5ba07d1150930ff2763ecf294cc9d723",
    "group_prosumers.py": "41b510f250ca2e03a9eabd8e1cfce9e3",
}
MENDELEY = "https://data.mendeley.com/datasets/8hj76bpzpv/1"
TRAFFIC_DOI = "10.17632/8hj76bpzpv.1"
TRAFFIC_NAME = "Dataset for traffic analysis in Casablanca, Morocco.xlsx"
TRAFFIC_URL = ("https://data.mendeley.com/public-files/datasets/8hj76bpzpv/files/"
               "9da089a4-8fa9-489b-942a-ee7e04d2d861/file_downloaded")
TRAFFIC_SHA = "4778abffbe3d7791afa58069fc8a98b6e89995174d4c64401d9367221c42d17d"
EXPECTED = {
    Path(tariff, f"{prefix}{k}-{10*k}.txt")
    for tariff, prefix in (("ToU", "r"), ("Flat", "rF"))
    for k in range(2, 21, 2)
}


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(path, algorithm="sha256"):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, algorithm).hexdigest()


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
                         encoding="utf-8")
    temporary.replace(path)


def download(path, url, algorithm, expected, doi, version, origin="primary"):
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(path.name + ".part")
    retrieved = None
    for attempt in range(4):
        if path.is_file() and digest(path, algorithm) == expected:
            break
        if partial.is_file() and digest(partial, algorithm) == expected:
            retrieved = datetime.fromtimestamp(partial.stat().st_mtime, timezone.utc).isoformat()
            partial.replace(path)
            break
        if attempt == 3:
            observed_file = partial if partial.exists() else path
            observed = digest(observed_file, algorithm) if observed_file.exists() else "no bytes"
            raise ValueError(f"{url}: expected {algorithm} {expected}, got {observed}")
        offset = partial.stat().st_size if partial.is_file() else 0
        # An integrity failure can indicate a corrupt prefix. Retry from zero on later attempts.
        if attempt:
            offset = 0
        headers = {"User-Agent": "PRICE-RIDE research dataset acquisition"}
        if offset:
            headers["Range"] = f"bytes={offset}-"
        try:
            with urlopen(Request(url, headers=headers), timeout=40) as response:
                resume = (offset and response.status == 206
                          and response.headers.get("Content-Range", "").startswith(f"bytes {offset}-"))
                if response.status == 206 and not resume:
                    raise OSError("invalid partial content range")
                with partial.open("ab" if resume else "wb") as output:
                    shutil.copyfileobj(response, output)
        except OSError as exc:
            if attempt == 2:
                observed = digest(partial, algorithm) if partial.exists() else "no bytes"
                raise OSError(f"{url}: {exc}. Expected {algorithm} {expected}, got {observed}") from exc
        time.sleep(2 ** attempt)
    return {
        "name": path.name, "url": url, "origin": origin, "doi": doi, "version": version,
        "license": "CC BY 4.0", "retrieved_utc": retrieved or
        datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(),
        "bytes": path.stat().st_size, "md5": digest(path, "md5"), "sha256": digest(path),
        "published_checksum": f"{algorithm}:{expected}",
    }


def checked_members(archive):
    seen = set()
    for member in archive.infolist():
        path = PurePosixPath(member.filename)
        if (path.is_absolute() or ".." in path.parts or "\\" in member.filename or
                any(":" in part for part in path.parts) or
                stat.S_ISLNK(member.external_attr >> 16) or str(path).casefold() in seen):
            raise ValueError(f"unsafe or duplicate archive member: {member.filename}")
        seen.add(str(path).casefold())
    bad = archive.testzip()
    if bad:
        raise ValueError(f"ZIP CRC failure in {bad}")
    return archive.namelist()


def acquire_porto(root):
    raw = root / "datasets/porto/raw"
    dest = root / "datasets/porto/instances"
    records = []
    failures = {}
    for name, md5 in PORTO_FILES.items():
        url = f"{PORTO}/files/{name}?download=1"
        try:
            record = download(raw / name, url, "md5", md5, PORTO_DOI, "v4")
            if name.endswith(".zip"):
                with ZipFile(raw / name) as archive:
                    record["members"] = checked_members(archive)
                    if name == "Instances.zip":
                        sources = {}
                        for member in record["members"]:
                            parts = PurePosixPath(member).parts
                            if parts[0] != "__MACOSX" and len(parts) >= 2 and parts[-2] in (
                                    "ToU", "Flat") and parts[-1].endswith(".txt"):
                                rel = Path(*parts[-2:])
                                if rel in sources:
                                    raise ValueError(f"duplicate instance path {rel}")
                                sources[rel] = member
                        if sources.keys() != EXPECTED:
                            raise ValueError(f"unexpected instance inventory: {sorted(sources)}")
                        for rel, member in sorted(sources.items()):
                            target = dest / rel
                            target.parent.mkdir(parents=True, exist_ok=True)
                            content = archive.read(member)
                            if not target.exists() or target.read_bytes() != content:
                                temporary = target.with_suffix(".tmp")
                                temporary.write_bytes(content)
                                os.replace(temporary, target)
            records.append(record)
        except (ValueError, OSError) as exc:
            failures[name] = str(exc)
    result = {"records": records, "failures": failures}
    save_json(raw / "provenance.json", result)
    return result


def acquire_traffic(root, fallback_url=None):
    raw = root / "datasets/casablanca/raw"
    path = raw / TRAFFIC_NAME
    previous = raw / "provenance.json"
    earlier = json.loads(previous.read_text(encoding="utf-8")) if previous.exists() else {}
    if (earlier.get("status") == "verified" and path.is_file()
            and digest(path) == TRAFFIC_SHA):
        return earlier
    try:
        result = download(path, TRAFFIC_URL, "sha256", TRAFFIC_SHA, TRAFFIC_DOI, "v1")
    except (OSError, ValueError) as original:
        if fallback_url:
            try:
                result = download(path, fallback_url, "sha256", TRAFFIC_SHA, TRAFFIC_DOI,
                                  "v1", "author-associated byte-verified fallback")
                result["primary_failure"] = str(original)
            except (OSError, ValueError) as fallback:
                result = {"status": "BLOCKED", "primary": str(original), "fallback": str(fallback)}
        else:
            result = {"status": "BLOCKED", "primary": str(original)}
    if "sha256" in result:
        with ZipFile(path) as archive:
            result["members"] = checked_members(archive)
        result["status"] = "verified"
    save_json(previous, result)
    return result
