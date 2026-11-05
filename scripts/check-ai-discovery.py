#!/usr/bin/env python3
"""Fail the site build if basic AI/search discovery assets are missing or malformed.

This checks generated public/ rather than assuming Hugo source configuration is
the same as the deployed HTML. It does not make claims about search rankings.
"""
from __future__ import annotations

import html
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"
DOMAIN = "caoyide.com"
ARTICLE_JSON_RE = re.compile(
    r'<script\b[^>]*\btype=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.I | re.S,
)
CANONICAL_RE = re.compile(r'<link\b[^>]*\brel=["\']canonical["\'][^>]*>', re.I)
DESCRIPTION_RE = re.compile(r'<meta\b[^>]*\bname=["\']description["\'][^>]*>', re.I)
NOINDEX_RE = re.compile(r'<meta\b[^>]*\bname=["\']robots["\'][^>]*\bnoindex\b', re.I)


def fail(message: str, errors: list[str]) -> None:
    errors.append(message)


def read_required(path: Path, errors: list[str]) -> str:
    if not path.is_file():
        fail(f"missing discovery artifact: {path.relative_to(ROOT)}", errors)
        return ""
    value = path.read_text(encoding="utf-8", errors="replace")
    if not value.strip():
        fail(f"empty discovery artifact: {path.relative_to(ROOT)}", errors)
    return value


def nodes(value):
    if isinstance(value, dict):
        yield value
        for nested in value.values():
            yield from nodes(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from nodes(nested)


def check_article(path: Path, errors: list[str]) -> None:
    page = read_required(path, errors)
    if not page:
        return
    name = path.relative_to(PUBLIC).as_posix()
    if not CANONICAL_RE.search(page):
        fail(f"no canonical link: {name}", errors)
    if not DESCRIPTION_RE.search(page):
        fail(f"no description meta tag: {name}", errors)
    if NOINDEX_RE.search(page):
        fail(f"unexpected noindex on legal article: {name}", errors)

    raw_scripts = ARTICLE_JSON_RE.findall(page)
    if not raw_scripts:
        fail(f"no JSON-LD blocks: {name}", errors)
        return

    articles = []
    for raw in raw_scripts:
        try:
            payload = json.loads(html.unescape(raw.strip()))
            if isinstance(payload, str):
                payload = json.loads(payload)
        except (ValueError, TypeError) as exc:
            fail(f"invalid JSON-LD in {name}: {exc}", errors)
            continue
        articles.extend(node for node in nodes(payload) if node.get("@type") == "Article")

    if not articles:
        fail(f"no Article JSON-LD in {name}", errors)
        return
    if not any(
        item.get("headline")
        and item.get("datePublished")
        and isinstance(item.get("author"), dict)
        and item["author"].get("@id") == "https://caoyide.com/#attorney"
        for item in articles
    ):
        fail(f"Article missing headline/date/normalized lawyer author: {name}", errors)


def main() -> int:
    errors: list[str] = []
    robot_text = read_required(PUBLIC / "robots.txt", errors)
    llms_text = read_required(PUBLIC / "llms.txt", errors)
    xml_text = read_required(PUBLIC / "sitemap.xml", errors)
    read_required(PUBLIC / "laws" / "sitemap.xml", errors)
    for name in ("legal-graph.json", "legal-topic-graph.json", "legal-intent-graph.json"):
        raw = read_required(PUBLIC / name, errors)
        if raw:
            try:
                json.loads(raw)
            except json.JSONDecodeError as exc:
                fail(f"invalid machine-readable graph {name}: {exc}", errors)

    if robot_text:
        search_bot = re.search(
            r'(?im)^User-agent:\s*OAI-SearchBot\s*$\n(?:(?!User-agent:).)*?^Allow:\s*/\s*$',
            robot_text,
            re.M | re.I | re.S,
        )
        if not search_bot:
            fail("robots.txt does not explicitly allow OAI-SearchBot", errors)
        for entry in ("https://caoyide.com/sitemap.xml", "https://caoyide.com/laws/sitemap.xml"):
            if entry not in robot_text:
                fail(f"robots.txt missing sitemap: {entry}", errors)

    if llms_text:
        for entry in ("/daily/", "/hotspot-daily/", "/posts/", "legal-topic-graph.json", "legal-intent-graph.json"):
            if entry not in llms_text:
                fail(f"llms.txt missing discovery entry: {entry}", errors)

    urls: set[str] = set()
    if xml_text:
        try:
            root = ET.fromstring(xml_text)
            for node in root.iter():
                if node.tag.endswith("}loc") or node.tag == "loc":
                    if node.text:
                        urls.add(node.text.strip())
        except ET.ParseError as exc:
            fail(f"invalid sitemap.xml: {exc}", errors)
    if len(urls) < 10:
        fail(f"sitemap.xml has only {len(urls)} valid <loc> entries", errors)
    if any(urlsplit(url).hostname != DOMAIN for url in urls):
        fail("sitemap.xml includes a URL outside caoyide.com", errors)
    for route in ("/daily/", "/hotspot-daily/", "/posts/"):
        if not any(route in urlsplit(url).path for url in urls):
            fail(f"sitemap.xml contains no content URL under {route}", errors)

    for section in ("daily", "hotspot-daily"):
        candidates = sorted((PUBLIC / section).rglob("index.html")) if (PUBLIC / section).exists() else []
        # The section archive itself should not substitute for a published article.
        candidates = [p for p in candidates if p.parent.name != section]
        if not candidates:
            fail(f"no built article in {section}/", errors)
        else:
            check_article(candidates[-1], errors)

    if errors:
        for error in errors:
            print("ERROR:", error, file=sys.stderr)
        print(f"AI discovery checks failed: {len(errors)} issue(s)", file=sys.stderr)
        return 1
    print(f"AI discovery checks passed: {len(urls)} sitemap links, article metadata and bot rules verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
