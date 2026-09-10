#!/usr/bin/env python3
"""Build a machine-readable article↔law graph and enrich Article JSON-LD.

Runs only against generated public/ HTML, so it never changes page layout or source
Markdown. Matching is conservative: exact law-title/short-title mentions only, and
only pages that already declare an Article JSON-LD entity are considered.
"""

from __future__ import annotations

import html
import json
import re
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"
BASE = "https://caoyide.com"
GRAPH_PATH = PUBLIC / "legal-graph.json"

TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
TAG_RE = re.compile(r"<[^>]+>")
SCRIPT_RE = re.compile(
    r'(<script\b[^>]*\btype=(?:["\']application/ld\+json["\']|application/ld\+json)[^>]*>)(.*?)(</script>)',
    re.I | re.S,
)
SPACE_RE = re.compile(r"\s+")
CHINESE_RE = re.compile(r"[\u4e00-\u9fff]")


def clean_text(value: str) -> str:
    value = re.sub(r"<(script|style)\b[^>]*>.*?</\1>", " ", value, flags=re.I | re.S)
    value = TAG_RE.sub(" ", value)
    return SPACE_RE.sub(" ", html.unescape(value)).strip()


def page_url(path: Path) -> str:
    rel = path.relative_to(PUBLIC).as_posix()
    if rel == "index.html":
        return BASE + "/"
    if rel.endswith("/index.html"):
        return BASE + "/" + rel[:-10]
    return BASE + "/" + rel


def title_of(text: str, fallback: str) -> str:
    match = TITLE_RE.search(text)
    if not match:
        return fallback
    title = clean_text(match.group(1))
    for suffix in (" | 法律文库", " - 法律文库", " | 曹义德律师", " - 曹义德律师"):
        if title.endswith(suffix):
            title = title[: -len(suffix)].strip()
    return title or fallback


def law_aliases(title: str) -> list[str]:
    candidates = [title]
    short = re.sub(r"^中华人民共和国", "", title).strip()
    short = re.sub(r"（.*?）|\(.*?\)", "", short).strip()
    if short != title:
        candidates.append(short)
    aliases = []
    for item in candidates:
        if len(CHINESE_RE.findall(item)) >= 4 and item not in aliases:
            aliases.append(item)
    return aliases


def build_law_catalog() -> list[dict]:
    laws: list[dict] = []
    for path in sorted((PUBLIC / "laws").rglob("*.html")):
        rel = path.relative_to(PUBLIC / "laws").as_posix()
        if rel == "404.html" or rel.startswith("category/"):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        title = title_of(text, unquote(path.stem))
        aliases = law_aliases(title)
        if not aliases:
            continue
        url = page_url(path)
        laws.append({"id": url + "#law", "title": title, "url": url, "aliases": aliases})
    return laws


def walk_json(node):
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from walk_json(value)
    elif isinstance(node, list):
        for item in node:
            yield from walk_json(item)


def parse_jsonld(raw: str):
    """Parse normal, HTML-escaped, or one-level double-encoded JSON-LD."""
    value = json.loads(html.unescape(raw.strip()))
    if isinstance(value, str):
        candidate = html.unescape(value.strip())
        if candidate.startswith(("{", "[")):
            value = json.loads(candidate)
    return value


def has_article_jsonld(text: str) -> bool:
    for match in SCRIPT_RE.finditer(text):
        try:
            data = parse_jsonld(match.group(2))
        except (json.JSONDecodeError, TypeError):
            continue
        if any(node.get("@type") == "Article" for node in walk_json(data) if isinstance(node, dict)):
            return True
    return False


def inject_citations(text: str, law_nodes: list[dict], current_url: str) -> tuple[str, bool]:
    if not law_nodes:
        return text, False
    changed = False
    refs = [
        {"@type": "Legislation", "@id": law["id"], "name": law["title"], "url": law["url"]}
        for law in law_nodes
    ]

    def repl(match: re.Match[str]) -> str:
        nonlocal changed
        try:
            data = parse_jsonld(match.group(2))
        except (json.JSONDecodeError, TypeError):
            return match.group(0)

        touched = False
        for node in walk_json(data):
            if not isinstance(node, dict) or node.get("@type") != "Article":
                continue
            node["citation"] = refs
            node["about"] = refs
            node.setdefault("mainEntityOfPage", {"@type": "WebPage", "@id": current_url})
            touched = True
        if not touched:
            return match.group(0)
        changed = True
        rendered = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        return match.group(1) + rendered + match.group(3)

    return SCRIPT_RE.sub(repl, text), changed


def main() -> int:
    if not (PUBLIC / "laws").exists():
        raise SystemExit("legal graph: public/laws is missing")

    laws = build_law_catalog()
    if len(laws) < 100:
        raise SystemExit(f"legal graph: suspicious law catalog size: {len(laws)}")

    pages = []
    edges = []
    enriched = 0
    article_pages = 0

    for path in sorted(PUBLIC.rglob("*.html")):
        rel = path.relative_to(PUBLIC).as_posix()
        if rel.startswith("laws/") or rel == "404.html":
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if not has_article_jsonld(text):
            continue
        article_pages += 1
        visible = clean_text(text)
        if len(visible) < 80:
            continue
        current_url = page_url(path)
        page_title = title_of(text, current_url)

        matched = []
        for law in laws:
            if any(alias in visible for alias in law["aliases"]):
                matched.append(law)
        matched.sort(key=lambda item: max(len(a) for a in item["aliases"]), reverse=True)
        matched = matched[:12]
        if not matched:
            continue

        pages.append({"id": current_url + "#article", "title": page_title, "url": current_url})
        for law in matched:
            edges.append({"from": current_url + "#article", "to": law["id"], "type": "mentionsLaw"})

        updated, changed = inject_citations(text, matched, current_url)
        if changed:
            path.write_text(updated, encoding="utf-8")
            enriched += 1

    used_law_ids = {edge["to"] for edge in edges}
    graph = {
        "@context": {
            "@vocab": "https://schema.org/",
            "mentionsLaw": {"@id": "citation", "@type": "@id"},
        },
        "generatedBy": "caoyide-blog/scripts/enrich-legal-graph.py",
        "site": BASE + "/",
        "nodes": {
            "articles": pages,
            "laws": [{k: v for k, v in law.items() if k != "aliases"} for law in laws if law["id"] in used_law_ids],
        },
        "edges": edges,
        "stats": {
            "lawCatalog": len(laws),
            "articlePagesScanned": article_pages,
            "linkedArticles": len(pages),
            "edges": len(edges),
            "enrichedHtml": enriched,
        },
    }
    GRAPH_PATH.write_text(json.dumps(graph, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(
        f"Legal graph complete: {len(laws)} law pages indexed; {article_pages} Article page(s) scanned; "
        f"{len(pages)} linked; {len(edges)} edges; {enriched} HTML page(s) enriched."
    )
    if article_pages == 0:
        raise SystemExit("ERROR: no Article JSON-LD found; legal graph enrichment did not run.")
    if pages and enriched == 0:
        raise SystemExit("ERROR: laws were matched but Article JSON-LD was not enriched.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
