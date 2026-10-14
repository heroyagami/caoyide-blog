#!/usr/bin/env python3
"""Mirror public DailyNews hotspot Markdown into Hugo. Stdlib only."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
SOURCE_REPO = "heroyagami/DailyNews"
SOURCE_BRANCH = "main"
SOURCE_PATTERN = re.compile(r"^content/hotspot-daily/(\d{4})/(\d{2})/(\d{4}-\d{2}-\d{2})\.md$")
MAX_FILES = 600
MAX_FILE_BYTES = 300_000


def fetch(url: str) -> bytes:
    api = "api.github.com" in url
    headers = {"User-Agent": "caoyide-hotspot-sync",
               "Accept": "application/vnd.github+json" if api else "text/plain"}
    token = os.environ.get("GITHUB_TOKEN", "")
    if token and api:
        headers["Authorization"] = f"Bearer {token}"
    with urlopen(Request(url, headers=headers), timeout=35) as response:
        return response.read(4_000_001 if api else MAX_FILE_BYTES + 1)


def validate(path: str, raw: bytes, source_sha: str) -> None:
    if not raw or len(raw) > MAX_FILE_BYTES:
        raise ValueError(f"{path}: empty or oversized Markdown")
    calculated = hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest()
    if calculated != source_sha:
        raise ValueError(f"{path}: source SHA mismatch (upstream changed during sync)")
    value = raw.decode("utf-8-sig")
    if not value.startswith("---\n") or "\n---\n" not in value:
        raise ValueError(f"{path}: missing YAML front matter")
    fm, body = value.split("\n---\n", 1)
    date = Path(path).stem
    if not re.search(rf"(?m)^date:\s*['\"]?{re.escape(date)}['\"]?\s*$", fm):
        raise ValueError(f"{path}: invalid date")
    for field in ("title", "author", "categories", "tags", "description"):
        if not re.search(rf"(?m)^{field}:\s*\S+", fm):
            raise ValueError(f"{path}: missing {field}")
    if not re.search(r"(?m)^draft:\s*false\s*$", fm):
        raise ValueError(f"{path}: only published articles can be synchronized")
    if not re.search(r"(?m)^type:\s*['\"]?hotspot-deep-daily['\"]?\s*$", fm):
        raise ValueError(f"{path}: wrong content type")
    if not re.search(r"(?m)^# 今日热点深度文章池\s*$", body):
        raise ValueError(f"{path}: missing article-pool heading")
    if not re.search(r"(?m)^## 1\.\s+\S+", body) or len(body.strip()) < 300:
        raise ValueError(f"{path}: article body invalid")


def main() -> int:
    listing = f"https://api.github.com/repos/{SOURCE_REPO}/git/trees/{SOURCE_BRANCH}?recursive=1"
    tree = json.loads(fetch(listing).decode("utf-8"))
    if tree.get("truncated"):
        raise RuntimeError("Truncated upstream tree; aborting partial sync")
    entries = []
    for obj in tree.get("tree", []):
        path = obj.get("path", "")
        match = SOURCE_PATTERN.fullmatch(path)
        if not match or obj.get("type") != "blob":
            continue
        year, month, date = match.groups()
        if date[:4] != year or date[5:7] != month:
            raise ValueError(f"Bad upstream path: {path}")
        if obj.get("size", 0) > MAX_FILE_BYTES:
            raise ValueError(f"Oversized upstream Markdown: {path}")
        entries.append((path, obj["sha"]))
    entries.sort()
    if not entries or len(entries) > MAX_FILES:
        raise RuntimeError("No articles or too many articles in upstream")
    incoming = []
    for path, sha in entries:
        url = f"https://raw.githubusercontent.com/{SOURCE_REPO}/{SOURCE_BRANCH}/{quote(path)}"
        raw = fetch(url)
        validate(path, raw, sha)
        dest = ROOT / path
        if ROOT not in dest.parents:
            raise ValueError(f"Unsafe destination: {path}")
        incoming.append((dest, raw))
    changed = 0
    for dest, raw in incoming:
        if dest.is_file() and dest.read_bytes() == raw:
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(raw)
        print(f"SYNCED {dest.relative_to(ROOT)}")
        changed += 1
    print(f"DailyNews: {len(entries)} source articles; {changed} updated")
    latest_date = Path(entries[-1][0]).stem
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as out:
            out.write(f"updated={changed}\nlatest_date={latest_date}\n")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"DailyNews sync FAILED: {exc}", file=sys.stderr)
        raise SystemExit(1)
