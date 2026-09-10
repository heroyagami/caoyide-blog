#!/usr/bin/env python3
"""Build search-intent → topic → article → law → practice-area graph.

This script only writes machine-readable build artifacts under public/. It does
not alter visible HTML, Markdown, CSS, cards, sidebars, or page layout.

Intent matching is deliberately conservative: an intent can match an article
only when that article was already assigned to the intent's parent legal topic
by the previous topic graph stage.
"""

from __future__ import annotations

import html
import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"
CONFIG_PATH = ROOT / "data" / "legal-search-intents.json"
ARTICLE_TOPICS_PATH = PUBLIC / "article-related-topics.json"
ARTICLE_LAWS_PATH = PUBLIC / "article-related-laws.json"
TOPIC_GRAPH_PATH = PUBLIC / "legal-topic-graph.json"
GRAPH_PATH = PUBLIC / "legal-intent-graph.json"
REVERSE_PATH = PUBLIC / "legal-intent-reverse.json"
ARTICLE_INTENTS_PATH = PUBLIC / "article-related-intents.json"
BASE = "https://caoyide.com"
WARN_ARTICLES_PER_INTENT = 60
HARD_MAX_ARTICLES_PER_INTENT = 150
MAX_INTENTS_PER_ARTICLE = 6

TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
TAG_RE = re.compile(r"<[^>]+>")
SCRIPT_RE = re.compile(
    r'(<script\b[^>]*\btype=(?:["\']application/ld\+json["\']|application/ld\+json)[^>]*>)(.*?)(</script>)',
    re.I | re.S,
)
SPACE_RE = re.compile(r"\s+")


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
    for suffix in (" | 曹义德律师", " - 曹义德律师"):
        if title.endswith(suffix):
            title = title[: -len(suffix)].strip()
    return title or fallback


def walk_json(node):
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from walk_json(value)
    elif isinstance(node, list):
        for item in node:
            yield from walk_json(item)


def parse_jsonld(raw: str):
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
        if any(isinstance(node, dict) and node.get("@type") == "Article" for node in walk_json(data)):
            return True
    return False


def load_json(path: Path):
    if not path.exists():
        raise SystemExit(f"intent graph: required build artifact missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def load_config() -> list[dict]:
    data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    intents = data.get("intents", [])
    blocked = set(data.get("blockedAliases", []))
    if not isinstance(intents, list) or not intents:
        raise SystemExit("intent graph: no configured intents")

    ids = [item.get("id") for item in intents]
    names = [item.get("name") for item in intents]
    if None in ids or len(ids) != len(set(ids)):
        raise SystemExit("intent graph: duplicate or missing intent id")
    if None in names or len(names) != len(set(names)):
        raise SystemExit("intent graph: duplicate or missing intent name")

    alias_owner: dict[str, str] = {}
    for item in intents:
        parent = item.get("parentTopic")
        aliases = item.get("aliases", [])
        intent_type = item.get("intentType")
        if not parent or not intent_type or not isinstance(aliases, list) or not aliases:
            raise SystemExit(f"intent graph: incomplete intent config: {item.get('name')}")
        cleaned: list[str] = []
        for alias in aliases:
            if not isinstance(alias, str):
                raise SystemExit(f"intent graph: non-string alias in {item.get('name')}")
            alias = alias.strip()
            if not alias or alias in blocked:
                continue
            previous = alias_owner.get(alias)
            if previous and previous != item["id"]:
                raise SystemExit(f"intent graph: ambiguous alias collision: {alias}")
            alias_owner[alias] = item["id"]
            if alias not in cleaned:
                cleaned.append(alias)
        if not cleaned:
            raise SystemExit(f"intent graph: intent has no usable aliases: {item.get('name')}")
        item["aliases"] = cleaned
    return intents


def extract_related_topic_ids(record: dict) -> set[str]:
    values = record.get("related_topics", [])
    result: set[str] = set()
    for item in values:
        if isinstance(item, dict) and item.get("id"):
            result.add(item["id"])
        elif isinstance(item, str):
            result.add(item)
    return result


def match_intents(visible: str, topic_ids: set[str], intents: list[dict]) -> list[dict]:
    matched: list[dict] = []
    for intent in intents:
        if intent["parentTopic"] not in topic_ids:
            continue
        hits = [alias for alias in intent["aliases"] if alias in visible]
        if hits:
            matched.append({**intent, "matchedAliases": hits})
    matched.sort(key=lambda item: (max(len(alias) for alias in item["matchedAliases"]), len(item["matchedAliases"])), reverse=True)
    return matched[:MAX_INTENTS_PER_ARTICLE]


def main() -> int:
    intents = load_config()
    article_topics_doc = load_json(ARTICLE_TOPICS_PATH)
    article_topics = article_topics_doc.get("articles") or {}
    article_laws_doc = load_json(ARTICLE_LAWS_PATH)
    article_laws = article_laws_doc.get("articles") or {}
    topic_graph = load_json(TOPIC_GRAPH_PATH)

    topic_nodes = topic_graph.get("nodes", {}).get("topics", [])
    practice_nodes = topic_graph.get("nodes", {}).get("practiceAreas", [])
    person = topic_graph.get("nodes", {}).get("person") or topic_graph.get("person")
    known_topic_ids = {item.get("id") for item in topic_nodes if isinstance(item, dict)}
    unknown_parents = sorted({item["parentTopic"] for item in intents} - known_topic_ids)
    if unknown_parents:
        raise SystemExit(f"intent graph: configured parent topic(s) missing from topic graph: {unknown_parents[:5]}")

    page_nodes: dict[str, dict] = {}
    intent_article_edges: list[dict] = []
    article_intents: dict[str, dict] = {}
    intent_to_articles: dict[str, list[dict]] = defaultdict(list)
    article_pages = 0

    for path in sorted(PUBLIC.rglob("*.html")):
        rel = path.relative_to(PUBLIC).as_posix()
        if rel.startswith("laws/") or rel == "404.html":
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if not has_article_jsonld(text):
            continue
        article_pages += 1
        url = page_url(path)
        topic_record = article_topics.get(url)
        if not isinstance(topic_record, dict):
            continue
        topic_ids = extract_related_topic_ids(topic_record)
        if not topic_ids:
            continue
        matched = match_intents(clean_text(text), topic_ids, intents)
        if not matched:
            continue

        article_id = topic_record.get("articleId") or (url + "#article")
        title = topic_record.get("title") or title_of(text, url)
        page_nodes[article_id] = {"id": article_id, "title": title, "url": url}
        related = []
        for intent in matched:
            related.append({"id": intent["id"], "name": intent["name"], "intentType": intent["intentType"], "parentTopic": intent["parentTopic"], "matchedAliases": intent["matchedAliases"]})
            intent_article_edges.append({"from": intent["id"], "to": article_id, "type": "answersIntent", "matchedAliases": intent["matchedAliases"]})
            intent_to_articles[intent["id"]].append({"id": article_id, "title": title, "url": url, "matchedAliases": intent["matchedAliases"]})
        article_intents[url] = {"articleId": article_id, "title": title, "related_intents": related}

    law_by_intent: dict[str, dict[str, dict]] = defaultdict(dict)
    for url, record in article_intents.items():
        law_record = article_laws.get(url, {})
        laws = law_record.get("related_laws", []) if isinstance(law_record, dict) else []
        intent_ids = [item["id"] for item in record["related_intents"]]
        for law in laws:
            if not isinstance(law, dict) or not law.get("id"):
                continue
            normalized = {"id": law["id"], "title": law.get("title"), "url": law.get("url")}
            for intent_id in intent_ids:
                law_by_intent[intent_id][law["id"]] = normalized

    intent_nodes = []
    intent_topic_edges = []
    intent_law_edges = []
    warnings: list[str] = []
    for intent in intents:
        article_count = len(intent_to_articles.get(intent["id"], []))
        law_count = len(law_by_intent.get(intent["id"], {}))
        intent_nodes.append({"id": intent["id"], "name": intent["name"], "intentType": intent["intentType"], "parentTopic": intent["parentTopic"], "aliases": intent["aliases"], "articleCount": article_count, "lawCount": law_count})
        intent_topic_edges.append({"from": intent["id"], "to": intent["parentTopic"], "type": "isPartOfTopic"})
        for law in law_by_intent.get(intent["id"], {}).values():
            intent_law_edges.append({"from": intent["id"], "to": law["id"], "type": "supportedByLaw"})
        if article_count == 0:
            warnings.append(f"orphan intent: {intent['name']} has no matching article")
        elif law_count == 0:
            warnings.append(f"intent without law relation: {intent['name']} ({article_count} article(s))")
        if article_count > HARD_MAX_ARTICLES_PER_INTENT:
            raise SystemExit(f"intent graph: suspiciously broad intent {intent['name']}: {article_count} articles")
        if article_count > WARN_ARTICLES_PER_INTENT:
            warnings.append(f"high fan-in: {intent['name']} is linked from {article_count} articles")

    duplicate_edges = len(intent_article_edges) - len({(e["from"], e["to"], e["type"]) for e in intent_article_edges})
    if duplicate_edges:
        raise SystemExit(f"intent graph: {duplicate_edges} duplicate intent→article edge(s)")

    reverse = {intent["id"]: {"name": intent["name"], "intentType": intent["intentType"], "parentTopic": intent["parentTopic"], "articles": sorted(intent_to_articles.get(intent["id"], []), key=lambda x: x["title"]), "laws": sorted(law_by_intent.get(intent["id"], {}).values(), key=lambda x: x.get("title") or "")} for intent in intents}

    graph = {
        "@context": {"@vocab": "https://schema.org/", "answersIntent": {"@id": "mainEntity", "@type": "@id"}, "supportedByLaw": {"@id": "citation", "@type": "@id"}},
        "generatedBy": "caoyide-blog/scripts/build-legal-search-intent-graph.py",
        "site": BASE + "/",
        "nodes": {"person": person, "practiceAreas": practice_nodes, "topics": topic_nodes, "intents": intent_nodes, "articles": list(page_nodes.values())},
        "edges": {"intentToTopic": intent_topic_edges, "intentToArticle": intent_article_edges, "intentToLaw": intent_law_edges},
        "stats": {"articlePagesScanned": article_pages, "configuredIntents": len(intents), "linkedIntents": sum(1 for node in intent_nodes if node["articleCount"] > 0), "linkedArticles": len(page_nodes), "intentArticleEdges": len(intent_article_edges), "intentLawEdges": len(intent_law_edges), "warnings": len(warnings)},
    }

    GRAPH_PATH.write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8")
    REVERSE_PATH.write_text(json.dumps(reverse, ensure_ascii=False, indent=2), encoding="utf-8")
    ARTICLE_INTENTS_PATH.write_text(json.dumps(article_intents, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Intent graph complete: {article_pages} Article page(s) scanned; {graph['stats']['linkedIntents']}/{len(intents)} intent(s) linked; {len(page_nodes)} linked article(s); {len(intent_article_edges)} intent→article edge(s); {len(intent_law_edges)} intent→law edge(s); {len(warnings)} warning(s).")
    for warning in warnings:
        print("WARNING:", warning)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
