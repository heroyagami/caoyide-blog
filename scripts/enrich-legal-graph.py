#!/usr/bin/env python3
"""Build a machine-readable article↔law graph and enrich Article JSON-LD.

This runs only against generated ``public/`` HTML, so it never changes page layout
or article Markdown. Matching stays conservative: generated aliases require at
least four Chinese characters, while shorter aliases must be explicitly curated
in ``data/legal-law-aliases.json``.
"""

from __future__ import annotations

import html
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"
BASE = "https://caoyide.com"
GRAPH_PATH = PUBLIC / "legal-graph.json"
REVERSE_PATH = PUBLIC / "legal-graph-reverse.json"
RELATED_PATH = PUBLIC / "article-related-laws.json"
ALIASES_PATH = ROOT / "data" / "legal-law-aliases.json"
MAX_LAWS_PER_ARTICLE = 12
WARN_ARTICLES_PER_LAW = 180
HARD_MAX_ARTICLES_PER_LAW = 330

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


def load_alias_config() -> tuple[dict[str, list[str]], set[str]]:
    if not ALIASES_PATH.exists():
        return {}, set()
    data = json.loads(ALIASES_PATH.read_text(encoding="utf-8"))
    aliases = data.get("aliases", {})
    blocked = set(data.get("blockedAliases", []))
    if not isinstance(aliases, dict) or not isinstance(blocked, set):
        raise SystemExit("legal graph: invalid legal-law-aliases.json structure")
    normalized: dict[str, list[str]] = {}
    for title, values in aliases.items():
        if not isinstance(title, str) or not isinstance(values, list):
            raise SystemExit("legal graph: invalid alias entry")
        cleaned = []
        for alias in values:
            if not isinstance(alias, str):
                raise SystemExit(f"legal graph: alias for {title!r} is not a string")
            alias = alias.strip()
            if alias and alias not in blocked and alias not in cleaned:
                cleaned.append(alias)
        normalized[title.strip()] = cleaned
    return normalized, blocked


def generated_aliases(title: str, blocked: set[str]) -> list[str]:
    candidates = [title]
    short = re.sub(r"^中华人民共和国", "", title).strip()
    short = re.sub(r"（.*?）|\(.*?\)", "", short).strip()
    if short != title:
        candidates.append(short)
    aliases: list[str] = []
    for item in candidates:
        if item in blocked:
            continue
        if len(CHINESE_RE.findall(item)) >= 4 and item not in aliases:
            aliases.append(item)
    return aliases


def build_law_catalog(curated: dict[str, list[str]], blocked: set[str]) -> list[dict]:
    laws: list[dict] = []
    for path in sorted((PUBLIC / "laws").rglob("*.html")):
        rel = path.relative_to(PUBLIC / "laws").as_posix()
        if rel == "404.html" or rel.startswith("category/"):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        title = title_of(text, unquote(path.stem))
        aliases = generated_aliases(title, blocked)
        for alias in curated.get(title, []):
            if alias not in aliases and alias not in blocked:
                aliases.append(alias)
        if not aliases:
            continue
        url = page_url(path)
        laws.append({"id": url + "#law", "title": title, "url": url, "aliases": aliases})
    return laws


def validate_catalog(laws: list[dict], curated: dict[str, list[str]]) -> list[str]:
    warnings: list[str] = []
    ids = [law["id"] for law in laws]
    titles = [law["title"] for law in laws]
    if len(ids) != len(set(ids)):
        duplicates = [item for item, count in Counter(ids).items() if count > 1]
        raise SystemExit(f"legal graph: duplicate law ids: {duplicates[:5]}")
    if len(titles) != len(set(titles)):
        duplicates = [item for item, count in Counter(titles).items() if count > 1]
        warnings.append(f"duplicate law titles detected: {duplicates[:5]}")

    law_titles = set(titles)
    unknown_curated = sorted(set(curated) - law_titles)
    if unknown_curated:
        warnings.append(
            "curated aliases reference law titles not present in current library: "
            + ", ".join(unknown_curated[:8])
        )

    alias_owner: dict[str, str] = {}
    collisions: list[tuple[str, str, str]] = []
    for law in laws:
        for alias in law["aliases"]:
            previous = alias_owner.get(alias)
            if previous and previous != law["id"]:
                collisions.append((alias, previous, law["id"]))
            else:
                alias_owner[alias] = law["id"]
    if collisions:
        sample = "; ".join(alias for alias, _, _ in collisions[:5])
        raise SystemExit(f"legal graph: ambiguous alias collision(s): {sample}")
    return warnings


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


def match_laws(visible: str, laws: list[dict]) -> list[dict]:
    matched = []
    for law in laws:
        hits = [alias for alias in law["aliases"] if alias in visible]
        if hits:
            matched.append({**law, "matchedAliases": hits})
    matched.sort(
        key=lambda item: max(len(alias) for alias in item["matchedAliases"]),
        reverse=True,
    )
    return matched[:MAX_LAWS_PER_ARTICLE]


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


def validate_graph(
    laws: list[dict],
    pages: list[dict],
    edges: list[dict],
    reverse: dict[str, list[dict]],
    article_pages: int,
    enriched: int,
) -> list[str]:
    warnings: list[str] = []
    law_ids = {law["id"] for law in laws}
    article_ids = {page["id"] for page in pages}

    dangling_laws = [edge for edge in edges if edge["to"] not in law_ids]
    dangling_articles = [edge for edge in edges if edge["from"] not in article_ids]
    if dangling_laws or dangling_articles:
        raise SystemExit(
            f"legal graph: dangling edges detected (law={len(dangling_laws)}, article={len(dangling_articles)})"
        )

    duplicate_edges = len(edges) - len({(edge["from"], edge["to"], edge["type"]) for edge in edges})
    if duplicate_edges:
        raise SystemExit(f"legal graph: {duplicate_edges} duplicate edge(s) detected")

    if article_pages == 0:
        raise SystemExit("ERROR: no Article JSON-LD found; legal graph enrichment did not run.")
    if pages and enriched == 0:
        raise SystemExit("ERROR: laws were matched but Article JSON-LD was not enriched.")

    for law_id, articles in reverse.items():
        count = len(articles)
        if count > HARD_MAX_ARTICLES_PER_LAW:
            raise SystemExit(f"legal graph: suspiciously broad law match {law_id}: {count} articles")
        if count > WARN_ARTICLES_PER_LAW:
            warnings.append(f"high fan-in: {law_id} is linked from {count} articles")
    return warnings


def main() -> int:
    if not (PUBLIC / "laws").exists():
        raise SystemExit("legal graph: public/laws is missing")

    curated, blocked = load_alias_config()
    laws = build_law_catalog(curated, blocked)
    if len(laws) < 100:
        raise SystemExit(f"legal graph: suspicious law catalog size: {len(laws)}")
    warnings = validate_catalog(laws, curated)

    pages: list[dict] = []
    edges: list[dict] = []
    related: dict[str, dict] = {}
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
        matched = match_laws(visible, laws)
        if not matched:
            continue

        article_id = current_url + "#article"
        pages.append({"id": article_id, "title": page_title, "url": current_url})
        related[current_url] = {
            "articleId": article_id,
            "title": page_title,
            "related_laws": [
                {
                    "id": law["id"],
                    "title": law["title"],
                    "url": law["url"],
                    "matchedAliases": law["matchedAliases"],
                }
                for law in matched
            ],
        }
        for law in matched:
            edges.append(
                {
                    "from": article_id,
                    "to": law["id"],
                    "type": "mentionsLaw",
                    "matchedAliases": law["matchedAliases"],
                }
            )

        updated, changed = inject_citations(text, matched, current_url)
        if changed:
            path.write_text(updated, encoding="utf-8")
            enriched += 1

    reverse_map: dict[str, list[dict]] = defaultdict(list)
    page_by_id = {page["id"]: page for page in pages}
    for edge in edges:
        article = page_by_id[edge["from"]]
        reverse_map[edge["to"]].append(
            {
                "id": article["id"],
                "title": article["title"],
                "url": article["url"],
                "matchedAliases": edge["matchedAliases"],
            }
        )
    for articles in reverse_map.values():
        articles.sort(key=lambda item: item["title"])

    warnings.extend(validate_graph(laws, pages, edges, reverse_map, article_pages, enriched))

    used_law_ids = set(reverse_map)
    graph_laws = []
    for law in laws:
        if law["id"] not in used_law_ids:
            continue
        graph_laws.append(
            {
                "id": law["id"],
                "title": law["title"],
                "url": law["url"],
                "aliases": law["aliases"],
                "referencedByCount": len(reverse_map[law["id"]]),
            }
        )

    graph = {
        "@context": {
            "@vocab": "https://schema.org/",
            "mentionsLaw": {"@id": "citation", "@type": "@id"},
        },
        "generatedBy": "caoyide-blog/scripts/enrich-legal-graph.py",
        "site": BASE + "/",
        "nodes": {"articles": pages, "laws": graph_laws},
        "edges": edges,
        "stats": {
            "lawCatalog": len(laws),
            "articlePagesScanned": article_pages,
            "linkedArticles": len(pages),
            "linkedLaws": len(used_law_ids),
            "edges": len(edges),
            "enrichedHtml": enriched,
            "warnings": len(warnings),
        },
        "warnings": warnings,
    }

    reverse_doc = {
        "generatedBy": "caoyide-blog/scripts/enrich-legal-graph.py",
        "site": BASE + "/",
        "laws": [
            {
                "id": law["id"],
                "title": law["title"],
                "url": law["url"],
                "articleCount": len(reverse_map[law["id"]]),
                "articles": reverse_map[law["id"]],
            }
            for law in laws
            if law["id"] in used_law_ids
        ],
    }

    GRAPH_PATH.write_text(json.dumps(graph, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    REVERSE_PATH.write_text(json.dumps(reverse_doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    RELATED_PATH.write_text(
        json.dumps(
            {
                "generatedBy": "caoyide-blog/scripts/enrich-legal-graph.py",
                "site": BASE + "/",
                "articles": related,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )

    print(
        f"Legal graph complete: {len(laws)} law pages indexed; {article_pages} Article page(s) scanned; "
        f"{len(pages)} linked article(s); {len(used_law_ids)} linked law(s); {len(edges)} edges; "
        f"{enriched} HTML page(s) enriched; {len(warnings)} warning(s)."
    )
    print(f"Reverse index: {REVERSE_PATH}")
    print(f"Related-law metadata: {RELATED_PATH}")
    for warning in warnings:
        print(f"WARNING: {warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
