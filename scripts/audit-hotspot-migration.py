#!/usr/bin/env python3
"""Read-only byte-for-byte verification of the legacy hotspot mirror."""
from __future__ import annotations
import argparse
import importlib.util
import json
import re
from pathlib import Path
from urllib.parse import quote

spec = importlib.util.spec_from_file_location("legacy_sync", Path(__file__).with_name("sync-dailynews.py"))
legacy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(legacy)

def verify(ref: str) -> int:
    if not re.fullmatch(r"[0-9a-f]{40}", ref):
        raise ValueError("Expected immutable source commit SHA")
    url = f"https://api.github.com/repos/{legacy.SOURCE_REPO}/git/trees/{ref}?recursive=1"
    tree = json.loads(legacy.fetch(url))
    if tree.get("truncated"):
        raise ValueError("Truncated source tree")
    entries = [(x["path"], x["sha"]) for x in tree["tree"]
               if x["type"] == "blob" and legacy.SOURCE_PATTERN.fullmatch(x["path"])]
    if not entries or len(entries) > legacy.MAX_FILES:
        raise ValueError("Unexpected source entry count")
    failures = []
    for path, sha in sorted(entries):
        year, month, date = legacy.SOURCE_PATTERN.fullmatch(path).groups()
        if date[:4] != year or date[5:7] != month:
            raise ValueError("Invalid source date path")
        raw = legacy.fetch(f"https://raw.githubusercontent.com/{legacy.SOURCE_REPO}/{ref}/{quote(path)}")
        legacy.validate(path, raw, sha)
        source = raw.decode("utf-8")
        if re.search(r"(?m)^url:\s*", source.split("\n---\n",1)[0]):
            raise ValueError("Unexpected source URL override")
        expected = source.replace("\n---\n", f'\nurl: "/hotspot-daily/{year}/{month}/{date}/"\n---\n', 1).encode("utf-8")
        target = legacy.ROOT / path
        if not target.is_file() or target.read_bytes() != expected:
            failures.append(path)
    if failures:
        print("MISSING OR DIFFERENT: " + ", ".join(failures))
        return 1
    print(f"PASS: {len(entries)} legacy hotspot files match byte-for-byte after stable URL transformation.")
    return 0

if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source-ref", required=True)
    raise SystemExit(verify(p.parse_args().source_ref))
