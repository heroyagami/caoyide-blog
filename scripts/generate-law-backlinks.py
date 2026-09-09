#!/usr/bin/env python3
"""Generate /laws/ -> article backlink data from Hugo related_laws front matter.

No third-party dependencies. Supports the TOML/YAML front matter shapes used in this
repository. The generated JSON is consumed by the VuePress client and is rebuilt on
every site build, so article/law links stay in sync with the content task.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content"
OUTPUT = ROOT / "law-site" / "docs" / ".vuepress" / "public" / "article-backlinks.json"


def split_frontmatter(text: str) -> tuple[str, str]:
    if text.startswith("+++\n"):
        end = text.find("\n+++", 4)
        return ("toml", text[4:end]) if end != -1 else ("", "")
    if text.startswith("---\n"):
        end = text.find("\n---", 4)
        return ("yaml", text[4:end]) if end != -1 else ("", "")
    return "", ""


def scalar(block: str, key: str) -> str:
    patterns = [
        rf"(?m)^\s*{re.escape(key)}\s*=\s*['\"]([^'\"]*)['\"]\s*$",
        rf"(?m)^\s*{re.escape(key)}\s*:\s*['\"]?([^\n'\"]+)['\"]?\s*$",
    ]
    for pattern in patterns:
        match = re.search(pattern, block)
        if match:
            return match.group(1).strip()
    return ""


def boolean(block: str, key: str, default: bool = False) -> bool:
    match = re.search(rf"(?mi)^\s*{re.escape(key)}\s*(?:=|:)\s*(true|false)\s*$", block)
    if not match:
        return default
    return match.group(1).lower() == "true"


def list_value(block: str, key: str) -> list[str]:
    inline = re.search(rf"(?ms)^\s*{re.escape(key)}\s*(?:=|:)\s*\[(.*?)\]\s*$", block)
    if inline:
        return [item.strip() for item in re.findall(r"['\"]([^'\"]+)['\"]", inline.group(1)) if item.strip()]

    yaml_block = re.search(
        rf"(?ms)^\s*{re.escape(key)}\s*:\s*\n((?:\s+-\s+[^\n]+\n?)*)",
        block,
    )
    if yaml_block:
        values: list[str] = []
        for item in re.findall(r"(?m)^\s+-\s+(.+?)\s*$", yaml_block.group(1)):
            cleaned = item.strip().strip("'\"")
            if cleaned:
                values.append(cleaned)
        return values
    return []


def law_url(ref: str) -> str | None:
    parts = [p for p in ref.strip().strip("/").split("/") if p]
    if len(parts) < 3:
        return None

    cat_dir = parts[0]
    prev = parts[-2]
    if not prev.endswith(".md"):
        return None

    law_file = prev[:-3]
    # Existing related-laws.html supports two historical formats:
    # cat/lawName/lawFile.md/article -> /laws/cat/lawName/lawFile.html
    # cat/lawFile.md/article         -> /laws/cat/lawFile/
    if len(parts) >= 4:
        law_name = parts[1]
        return f"/laws/{cat_dir}/{law_name}/{law_file}.html"
    return f"/laws/{cat_dir}/{law_file}/"


def content_url(path: Path, block: str) -> str:
    explicit = scalar(block, "url") or scalar(block, "permalink")
    if explicit:
        return explicit if explicit.startswith("/") else f"/{explicit}"

    rel = path.relative_to(CONTENT)
    slug = scalar(block, "slug") or path.stem

    if rel.parts and rel.parts[0] == "posts":
        return f"/posts/{slug}/"
    if rel.parts and rel.parts[0] == "daily":
        parent = "/".join(rel.parent.parts)
        return f"/{parent}/{slug}/"

    parent = "/".join(rel.parent.parts)
    return f"/{parent + '/' if parent != '.' else ''}{slug}/"


def main() -> int:
    backlinks: dict[str, list[dict[str, str]]] = {}

    for path in CONTENT.rglob("*.md"):
        if "laws" in path.parts:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        _, block = split_frontmatter(text)
        if not block or boolean(block, "draft", False):
            continue

        refs = list_value(block, "related_laws")
        if not refs:
            continue

        title = scalar(block, "title") or path.stem
        date = scalar(block, "date")
        url = content_url(path, block)
        item = {"title": title, "url": url}
        if date:
            item["date"] = date[:10]

        for ref in refs:
            target = law_url(ref)
            if not target:
                continue
            backlinks.setdefault(target, []).append(item)

    for items in backlinks.values():
        items.sort(key=lambda x: x.get("date", ""), reverse=True)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(backlinks, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Generated law backlinks: {len(backlinks)} law pages -> {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
