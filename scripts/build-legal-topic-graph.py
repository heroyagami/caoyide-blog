#!/usr/bin/env python3
"""Build a machine-readable topic→article→law→practice-area graph.

The script only reads generated public HTML plus curated configuration and writes
JSON build artifacts. It never changes visible page markup, article Markdown,
SCSS, cards, sidebars, or layout.
"""

from __future__ import annotations

import html
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"
CONFIG_PATH = ROOT / "data" / "legal-topic-entities.json"
ARTICLE_LAWS_PATH = PUBLIC / "article-related-laws.json"
GRAPH_PATH = PUBLIC / "legal-topic-graph.json"
REVERSE_PATH = PUBLIC / "legal-topic-reverse.json"
ARTICLE_TOPICS_PATH = PUBLIC / "article-related-topics.json"
BASE = "https://caoyide.com"
WARN_ARTICLES_PER_TOPIC = 100
HARD_MAX_ARTICLES_PER_TOPIC = 220
MAX_TOPICS_PER_ARTICLE = 8

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


def title_of(text: str, fallback: str) -> str:
    match = TITLE_RE.search(text)
    if not match:
        return fallback
    title = clean_text(match.group(1))
    for suffix in (" | 曹义德律师", " - 曹义德律师"):
        if title.endswith(suffix):
            title = title[: -len(suffix)].strip()
    return title or fallback


def page_url(path: Path) -> str:
    rel = path.relative_to(PUBLIC).as_posix()
    if rel == "index.html":
        return BASE + "/"
    if rel.endswith("/index.html"):
        return BASE + "/" + rel[:-10]
    return BASE + "/" + rel


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
        for node in walk_json(data):
            if isinstance(node, dict) and node.get("@type") == "Article":
                return True
    return False


def load_config() -> tuple[dict, list[dict], list[dict], set[str]]:
    if not CONFIG_PATH.exists():
        raise SystemExit("topic graph: data/legal-topic-entities.json is missing")
    data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    person = data.get("person") or {}
    areas = data.get("practiceAreas") or []
    topics = data.get("topics") or []
    blocked = set(data.get("blockedAliases") or [])
    if not person.get("id") or not person.get("name"):
        raise SystemExit("topic graph: person.id and person.name are required")
    if not areas or not topics:
        raise SystemExit("topic graph: practiceAreas and topics must not be empty")
    return person, areas, topics, blocked


def validate_config(person: dict, areas: list[dict], topics: list[dict], blocked: set[str]) -> list[str]:
    warnings: list[str] = []
    area_ids = [item.get("id") for item in areas]
    topic_ids = [item.get("id") for item in topics]
    if None in area_ids or None in topic_ids:
        raise SystemExit("topic graph: every practice area and topic needs an id")
    if len(area_ids) != len(set(area_ids)):
        raise SystemExit("topic graph: duplicate practiceArea id")
    if len(topic_ids) != len(set(topic_ids)):
        raise SystemExit("topic graph: duplicate topic id")

    area_by_id = {item["id"]: item for item in areas}
    alias_owner: dict[str, str] = {}
    for topic in topics:
        name = (topic.get("name") or "").strip()
        area_id = topic.get("practiceArea")
        aliases = topic.get("aliases") or []
        if not name or not aliases:
            raise SystemExit(f"topic graph: topic {topic.get('id')} has no name or aliases")
        if area_id not in area_by_id:
            raise SystemExit(f"topic graph: topic {name} references unknown practiceArea {area_id}")
        clean_aliases = []
        for alias in aliases:
            if not isinstance(alias, str):
                raise SystemExit(f"topic graph: alias for {name} must be a string")
            alias = alias.strip()
            if not alias or alias in blocked:
                continue
            owner = alias_owner.get(alias)
            if owner and owner != topic["id"]:
                raise SystemExit(f"topic graph: alias collision for {alias!r}")
            alias_owner[alias] = topic["id"]
            if alias not in clean_aliases:
                clean_aliases.append(alias)
        if not clean_aliases:
            raise SystemExit(f"topic graph: topic {name} has no usable aliases")
        topic["aliases"] = clean_aliases

    if not person.get("url"):
        warnings.append("person has no url")
    return warnings


def load_article_laws() -> dict[str, dict]:
    if not ARTICLE_LAWS_PATH.exists():
        raise SystemExit("topic graph: article-related-laws.json is missing; run enrich-legal-graph.py first")
    data = json.loads(ARTICLE_LAWS_PATH.read_text(encoding="utf-8"))
    return data.get("articles") or {}


def match_topics(visible: str, topics: list[dict]) -> list[dict]:
    matched = []
    for topic in topics:
        hits = [alias for alias in topic["aliases"] if alias in visible]
        if hits:
            matched.append({**topic, "matchedAliases": hits})
    matched.sort(
        key=lambda item: max(len(alias) for alias in item["matchedAliases"]),
        reverse=True,
    )
    return matched[:MAX_TOPICS_PER_ARTICLE]


def main() -> int:
    person, areas, topics, blocked = load_config()
    warnings = validate_config(person, areas, topics, blocked)
    article_laws = load_article_laws()

    area_by_id = {item["id"]: item for item in areas}
    topic_by_id = {item["id"]: item for item in topics}
    articles: dict[str, dict] = {}
    article_topics: dict[str, list[dict]] = {}
    topic_articles: dict[str, list[dict]] = defaultdict(list)
    topic_laws: dict[str, dict[str, dict]] = defaultdict(dict)
    law_topics: dict[str, dict[str, dict]] = defaultdict(dict)
    scanned = 0

    for path in sorted(PUBLIC.rglob("*.html")):
        rel = path.relative_to(PUBLIC).as_posix()
        if rel.startswith("laws/") or rel == "404.html":
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if not has_article_jsonld(text):
            continue
        scanned += 1
        visible = clean_text(text)
        if len(visible) < 80:
            continue
        matched = match_topics(visible, topics)
        if not matched:
            continue

        url = page_url(path)
        article_id = url + "#article"
        article = {"id": article_id, "title": title_of(text, url), "url": url}
        articles[article_id] = article
        article_topics[url] = []

        related_laws = (article_laws.get(url) or {}).get("related_laws") or []
        for topic in matched:
            topic_ref = {
                "id": topic["id"],
                "name": topic["name"],
                "practiceArea": topic["practiceArea"],
                "matchedAliases": topic["matchedAliases"],
            }
            article_topics[url].append(topic_ref)
            topic_articles[topic["id"]].append({**article, "matchedAliases": topic["matchedAliases"]})
            for law in related_laws:
                law_id = law.get("id")
                if not law_id:
                    continue
                topic_laws[topic["id"]][law_id] = {
                    "id": law_id,
                    "title": law.get("title"),
                    "url": law.get("url"),
                }
                law_topics[law_id][topic["id"]] = {
                    "id": topic["id"],
                    "name": topic["name"],
                    "practiceArea": topic["practiceArea"],
                }

    edges: list[dict] = []
    used_area_ids: set[str] = set()
    used_topic_ids: set[str] = set()

    for topic_id, linked_articles in topic_articles.items():
        linked_articles.sort(key=lambda item: item["title"])
        count = len(linked_articles)
        if count > HARD_MAX_ARTICLES_PER_TOPIC:
            raise SystemExit(f"topic graph: suspiciously broad topic match {topic_id}: {count} articles")
        if count > WARN_ARTICLES_PER_TOPIC:
            warnings.append(f"high fan-in: {topic_id} is linked from {count} articles")
        used_topic_ids.add(topic_id)
        area_id = topic_by_id[topic_id]["practiceArea"]
        used_area_ids.add(area_id)
        edges.append({"from": topic_id, "to": area_id, "type": "belongsToPracticeArea"})
        for article in linked_articles:
            edges.append({
                "from": topic_id,
                "to": article["id"],
                "type": "hasArticle",
                "matchedAliases": article["matchedAliases"],
            })
            edges.append({"from": article["id"], "to": topic_id, "type": "aboutTopic"})
        if not topic_laws.get(topic_id):
            warnings.append(f"topic has articles but no law relation: {topic_by_id[topic_id]['name']}")
        for law in topic_laws.get(topic_id, {}).values():
            edges.append({"from": topic_id, "to": law["id"], "type": "aggregatesLaw"})
            edges.append({"from": law["id"], "to": topic_id, "type": "relatedTopic"})

    for area_id in sorted(used_area_ids):
        edges.append({"from": area_id, "to": person["id"], "type": "expertiseOf"})

    unused_topics = [topic["name"] for topic in topics if topic["id"] not in used_topic_ids]
    if unused_topics:
        warnings.append("orphan topics with no matched articles: " + ", ".join(unused_topics))

    duplicate_edges = len(edges) - len({(e["from"], e["to"], e["type"]) for e in edges})
    if duplicate_edges:
        raise SystemExit(f"topic graph: {duplicate_edges} duplicate edge(s) detected")

    graph = {
        "@context": {
            "@vocab": "https://schema.org/",
            "aboutTopic": {"@id": "about", "@type": "@id"},
            "expertiseOf": {"@id": "provider", "@type": "@id"},
        },
        "generatedBy": "caoyide-blog/scripts/build-legal-topic-graph.py",
        "site": BASE + "/",
        "nodes": {
            "person": {"@type": "Person", **person},
            "practiceAreas": [
                {"@type": "Service", **area_by_id[area_id]}
                for area_id in sorted(used_area_ids)
            ],
            "topics": [
                {
                    "@type": "DefinedTerm",
                    "id": topic["id"],
                    "name": topic["name"],
                    "aliases": topic["aliases"],
                    "practiceArea": topic["practiceArea"],
                    "articleCount": len(topic_articles[topic["id"]]),
                    "lawCount": len(topic_laws.get(topic["id"], {})),
                }
                for topic in topics
                if topic["id"] in used_topic_ids
            ],
            "articles": list(articles.values()),
            "laws": sorted(
                {
                    law_id: law
                    for laws in topic_laws.values()
                    for law_id, law in laws.items()
                }.values(),
                key=lambda item: item.get("title") or item["id"],
            ),
        },
        "edges": edges,
        "stats": {
            "articlePagesScanned": scanned,
            "linkedArticles": len(articles),
            "configuredTopics": len(topics),
            "linkedTopics": len(used_topic_ids),
            "linkedPracticeAreas": len(used_area_ids),
            "topicArticleEdges": sum(len(v) for v in topic_articles.values()),
            "topicLawEdges": sum(len(v) for v in topic_laws.values()),
            "warnings": len(warnings),
        },
        "warnings": warnings,
    }

    reverse = {
        "generatedBy": "caoyide-blog/scripts/build-legal-topic-graph.py",
        "site": BASE + "/",
        "topics": [
            {
                "id": topic["id"],
                "name": topic["name"],
                "practiceArea": topic["practiceArea"],
                "articles": topic_articles.get(topic["id"], []),
                "laws": list(topic_laws.get(topic["id"], {}).values()),
            }
            for topic in topics
            if topic["id"] in used_topic_ids
        ],
        "laws": [
            {"id": law_id, "topics": list(topic_map.values())}
            for law_id, topic_map in sorted(law_topics.items())
        ],
        "practiceAreas": [
            {
                **area_by_id[area_id],
                "topics": [
                    {"id": topic["id"], "name": topic["name"]}
                    for topic in topics
                    if topic["id"] in used_topic_ids and topic["practiceArea"] == area_id
                ],
                "person": person,
            }
            for area_id in sorted(used_area_ids)
        ],
    }

    article_doc = {
        "generatedBy": "caoyide-blog/scripts/build-legal-topic-graph.py",
        "site": BASE + "/",
        "articles": {
            url: {
                "articleId": articles[url + "#article"]["id"],
                "title": articles[url + "#article"]["title"],
                "related_topics": refs,
            }
            for url, refs in article_topics.items()
        },
    }

    GRAPH_PATH.write_text(json.dumps(graph, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    REVERSE_PATH.write_text(json.dumps(reverse, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    ARTICLE_TOPICS_PATH.write_text(json.dumps(article_doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    print(
        f"Topic graph complete: {scanned} Article page(s) scanned; {len(articles)} linked article(s); "
        f"{len(used_topic_ids)}/{len(topics)} topic(s) linked; {len(used_area_ids)} practice area(s); "
        f"{sum(len(v) for v in topic_laws.values())} topic→law relation(s); {len(warnings)} warning(s)."
    )
    for warning in warnings:
        print(f"WARNING: {warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
