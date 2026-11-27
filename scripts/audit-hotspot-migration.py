#!/usr/bin/env python3
"""Offline verification of the exact DailyNews migration baseline; no network."""
import argparse
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data" / "dailynews-archive-manifest.json"
PATTERN = re.compile(r"^content/hotspot-daily/(\d{4})/(\d{2})/(\d{4}-\d{2}-\d{2})\.md$")

def blob_sha(data):
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()

def read_local(relative):
    path = ROOT / relative
    if not path.is_file() or ROOT not in path.resolve().parents:
        raise ValueError("Missing or unsafe local archive path: " + relative)
    return path.read_bytes()

def verify(source_ref=None):
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if manifest["schemaVersion"] != 1 or (source_ref and source_ref != manifest["sourceRevision"]):
        raise ValueError("Unexpected historical baseline")
    articles, other = manifest["articles"], manifest["otherFiles"]
    if len(articles) != 46 or len(other) != 3:
        raise ValueError("Unexpected archive counts")
    seen = set()
    for item in articles:
        path = item["path"]
        match = PATTERN.fullmatch(path)
        if not match or path in seen:
            raise ValueError("Bad or duplicate path: " + path)
        seen.add(path)
        year, month, date = match.groups()
        if date[:4] != year or date[5:7] != month:
            raise ValueError("Wrong archive date path")
        data = read_local(path)
        if blob_sha(data) != item["siteBlob"]:
            raise ValueError("Site baseline differs: " + path)
        marker = f'\nurl: "/hotspot-daily/{year}/{month}/{date}/"\n---\n'.encode()
        if data.count(marker) != 1:
            raise ValueError("Unexpected URL transform: " + path)
        source = data.replace(marker, b"\n---\n", 1)
        if blob_sha(source) != item["sourceBlob"]:
            raise ValueError("Original bytes cannot be reconstructed: " + path)
    for item in other:
        path = item["path"]
        if not path.startswith("docs/dailynews-legacy/") or path in seen:
            raise ValueError("Bad or duplicate legacy file path")
        seen.add(path)
        if blob_sha(read_local(path)) != item["sha"]:
            raise ValueError("Legacy document differs: " + path)
    print(f"PASS: {len(articles)} original hotspot Markdown files reconstruct exactly; {len(other)} other files match source blobs; no network.")
    return 0

if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source-ref")
    raise SystemExit(verify(p.parse_args().source_ref))
