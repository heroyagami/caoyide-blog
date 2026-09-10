#!/usr/bin/env python3
"""Normalize JSON-LD entity identity in built HTML without changing page layout.

The legacy Hugo partial emits useful structured data but some page-level Attorney
objects inherit the current article URL/description. This post-build pass keeps a
single stable lawyer identity and connects Article/CollectionPage objects to it.
"""

from __future__ import annotations

import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"
BASE = "https://caoyide.com/"
ATTORNEY_ID = BASE + "#attorney"
LAW_FIRM_ID = BASE + "#lawFirm"
LEGAL_SERVICE_ID = BASE + "#legalService"
WEBSITE_ID = BASE + "#website"
ATTORNEY_DESCRIPTION = (
    "曹义德律师，华中科技大学法学硕士，前反贪检察官，现任湖北江通律师事务所执业律师。"
    "主要从事刑事辩护、企业合规及民商事争议解决。"
)
# Hugo --minify may remove attribute quotes, so accept both quoted and unquoted forms.
SCRIPT_RE = re.compile(
    r'(<script\b[^>]*\btype=(?:["\']application/ld\+json["\']|application/ld\+json)[^>]*>)(.*?)(</script>)',
    re.I | re.S,
)


def normalize(node, page_url: str):
    if isinstance(node, list):
        for item in node:
            normalize(item, page_url)
        return
    if not isinstance(node, dict):
        return

    node_type = node.get("@type")
    node_id = node.get("@id")

    if node_id == ATTORNEY_ID or (node_type == "Attorney" and node.get("name") in {"曹义德", "曹义德律师"}):
        node["@id"] = ATTORNEY_ID
        node["url"] = BASE
        node["description"] = ATTORNEY_DESCRIPTION
        node.setdefault("worksFor", {"@id": LAW_FIRM_ID})

    if node_id == LAW_FIRM_ID:
        node["@id"] = LAW_FIRM_ID
        node.setdefault("url", BASE + "cases/")

    if node_id == LEGAL_SERVICE_ID:
        node["@id"] = LEGAL_SERVICE_ID
        node["provider"] = {"@id": ATTORNEY_ID}
        node.setdefault("parentOrganization", {"@id": LAW_FIRM_ID})

    if node_id == WEBSITE_ID or node_type == "WebSite":
        node["@id"] = WEBSITE_ID
        node["url"] = BASE
        node["publisher"] = {"@id": ATTORNEY_ID}

    if node_type == "Article":
        node.setdefault("@id", page_url + "#article")
        node["author"] = {"@id": ATTORNEY_ID}
        node["publisher"] = {"@id": ATTORNEY_ID}
        node["isPartOf"] = {"@id": WEBSITE_ID}
        node["mainEntityOfPage"] = {"@type": "WebPage", "@id": page_url}

    if node_type == "CollectionPage":
        node["isPartOf"] = {"@id": WEBSITE_ID}
        node["publisher"] = {"@id": ATTORNEY_ID}

    for value in list(node.values()):
        normalize(value, page_url)


def page_url_for(path: Path) -> str:
    rel = path.relative_to(PUBLIC).as_posix()
    if rel == "index.html":
        return BASE
    if rel.endswith("/index.html"):
        return BASE + rel[: -len("index.html")]
    return BASE + rel


def process(path: Path) -> tuple[bool, int, int]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    page_url = page_url_for(path)
    changed = False
    matched = 0
    parsed = 0

    def repl(match: re.Match[str]) -> str:
        nonlocal changed, matched, parsed
        matched += 1
        raw = html.unescape(match.group(2).strip())
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return match.group(0)
        parsed += 1
        before = json.dumps(data, ensure_ascii=False, sort_keys=True)
        normalize(data, page_url)
        after = json.dumps(data, ensure_ascii=False, sort_keys=True)
        if before == after:
            return match.group(0)
        changed = True
        rendered = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        return match.group(1) + rendered + match.group(3)

    updated = SCRIPT_RE.sub(repl, text)
    if changed:
        path.write_text(updated, encoding="utf-8")
    return changed, matched, parsed


def main() -> int:
    changed = 0
    matched = 0
    parsed = 0
    for path in PUBLIC.rglob("*.html"):
        did_change, count, parsed_count = process(path)
        matched += count
        parsed += parsed_count
        if did_change:
            changed += 1
    print(
        f"Structured-data normalization complete: {matched} JSON-LD block(s) found; "
        f"{parsed} parsed; {changed} HTML file(s) updated."
    )
    if matched == 0:
        raise SystemExit("ERROR: no JSON-LD blocks found in built HTML; schema normalization did not run.")
    if parsed == 0:
        raise SystemExit("ERROR: JSON-LD blocks were found but none could be parsed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
