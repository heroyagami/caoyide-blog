#!/usr/bin/env python3
"""Lightweight repository integrity checks for the lawyer content site.

Designed to be strict on URL/canonical collisions and malformed law references,
while only warning on editorial issues such as duplicate titles. Uses stdlib only.
"""

from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content"
LAW_DOCS = ROOT / "law-site" / "docs"


def frontmatter(text: str) -> str:
    if text.startswith("+++\n"):
        end = text.find("\n+++", 4)
        return text[4:end] if end != -1 else ""
    if text.startswith("---\n"):
        end = text.find("\n---", 4)
        return text[4:end] if end != -1 else ""
    return ""


def scalar(block: str, key: str) -> str:
    for pattern in (
        rf"(?m)^\s*{re.escape(key)}\s*=\s*['\"]([^'\"]*)['\"]\s*$",
        rf"(?m)^\s*{re.escape(key)}\s*:\s*['\"]?([^\n'\"]+)['\"]?\s*$",
    ):
        match = re.search(pattern, block)
        if match:
            return match.group(1).strip()
    return ""


def list_value(block: str, key: str) -> list[str]:
    inline = re.search(rf"(?ms)^\s*{re.escape(key)}\s*(?:=|:)\s*\[(.*?)\]\s*$", block)
    if inline:
        return [v.strip() for v in re.findall(r"['\"]([^'\"]+)['\"]", inline.group(1)) if v.strip()]
    yaml = re.search(rf"(?ms)^\s*{re.escape(key)}\s*:\s*\n((?:\s+-\s+[^\n]+\n?)*)", block)
    if yaml:
        return [v.strip().strip("'\"") for v in re.findall(r"(?m)^\s+-\s+(.+?)\s*$", yaml.group(1)) if v.strip()]
    return []


def is_draft(block: str) -> bool:
    match = re.search(r"(?mi)^\s*draft\s*(?:=|:)\s*(true|false)\s*$", block)
    return bool(match and match.group(1).lower() == "true")


def inferred_url(path: Path, block: str) -> str:
    explicit = scalar(block, "url") or scalar(block, "permalink")
    if explicit:
        return explicit
    rel = path.relative_to(CONTENT)
    slug = scalar(block, "slug") or path.stem
    if rel.parts and rel.parts[0] == "posts":
        return f"/posts/{slug}/"
    if rel.parts and rel.parts[0] == "daily":
        return "/" + "/".join((*rel.parent.parts, slug)) + "/"
    parent = rel.parent.as_posix()
    return f"/{'' if parent == '.' else parent + '/'}{slug}/"


def expected_law_source(ref: str) -> Path | None:
    parts = [p for p in ref.strip().strip("/").split("/") if p]
    if len(parts) < 3 or not parts[-2].endswith(".md"):
        return None
    if len(parts) >= 4:
        return LAW_DOCS.joinpath(*parts[:-1])
    return LAW_DOCS / parts[0] / parts[1]


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []
    urls: dict[str, Path] = {}
    canonicals: dict[str, Path] = {}
    titles: defaultdict[str, list[Path]] = defaultdict(list)

    for path in CONTENT.rglob("*.md"):
        if "laws" in path.parts:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        block = frontmatter(text)
        if not block or is_draft(block):
            continue

        title = scalar(block, "title")
        if title:
            titles[title].append(path)

        url = inferred_url(path, block)
        if url in urls:
            errors.append(f"URL collision: {url} -> {urls[url]} and {path}")
        else:
            urls[url] = path

        canonical = scalar(block, "canonicalUrl") or scalar(block, "canonical_url")
        if canonical:
            if canonical in canonicals:
                errors.append(f"Canonical collision: {canonical} -> {canonicals[canonical]} and {path}")
            else:
                canonicals[canonical] = path

        for ref in list_value(block, "related_laws"):
            expected = expected_law_source(ref)
            if expected is None:
                errors.append(f"Malformed related_laws reference in {path}: {ref}")
            elif not expected.exists():
                warnings.append(f"Law source not found for {path}: {ref} (expected {expected.relative_to(ROOT)})")

    for title, paths in titles.items():
        if len(paths) > 1:
            warnings.append("Duplicate title: " + title + " -> " + ", ".join(str(p.relative_to(ROOT)) for p in paths))

    print(f"Integrity scan: {len(urls)} public content URLs, {len(canonicals)} explicit canonicals")
    for warning in warnings:
        print(f"WARNING: {warning}")
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)

    if errors:
        print(f"Integrity check failed with {len(errors)} error(s).", file=sys.stderr)
        return 1
    print(f"Integrity check passed ({len(warnings)} warning(s)).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
