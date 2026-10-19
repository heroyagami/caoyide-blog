#!/usr/bin/env python3
"""Verify reader-facing routes without coupling publication checks to display copy."""
import json
import re
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1] / "public"
SECTIONS = ("posts", "hotspot-daily", "daily")
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}


def route(value):
    return unquote(urlsplit(value).path)


def stamp(item):
    return datetime.fromisoformat(item["date"].replace("Z", "+00:00"))


class Page(HTMLParser):
    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.links = []
        self.entry_dates = []
        self.footer_count = 0
        self.contact = False
        self.feed_nav_count = 0
        self.feed_nav = []
        self.feed_active = []
        self.feed_entries = []
        self.feed_entry_count = 0
        self.feed_summary_count = 0
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = set(attrs.get("class", "").split())
        ancestors = set().union(*(frame[1] for frame in self.stack)) if self.stack else set()
        if "site-footer" in classes:
            self.footer_count += 1
        if attrs.get("id") == "contact":
            self.contact = True
        if "journal-feed-nav" in classes:
            self.feed_nav_count += 1
        if "journal-entry" in classes:
            self.feed_entry_count += 1
        if "journal-entry-summary" in classes:
            self.feed_summary_count += 1
        if tag == "time" and "journal-entry-meta" in ancestors:
            self.entry_dates.append(attrs.get("datetime", ""))
        if tag == "a" and attrs.get("href"):
            href = route(attrs["href"])
            self.links.append((href, ancestors))
            if "journal-feed-nav" in ancestors:
                self.feed_nav.append(href)
                if attrs.get("aria-current") == "page":
                    self.feed_active.append(href)
            if "journal-entry" in ancestors:
                self.feed_entries.append(href)
        if tag not in VOID:
            self.stack.append((tag, classes))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                break


def read_page(path):
    file = ROOT / path.lstrip("/") / "index.html"
    assert file.is_file(), f"Missing built page: {path}"
    page = Page(file.read_text(encoding="utf-8"))
    assert page.footer_count == 1, f"{path}: expected one site footer"
    return page


def main():
    index = json.loads((ROOT / "search/index.json").read_text(encoding="utf-8"))
    articles = {route(item["permalink"]): item for item in index}
    assert len(articles) == len(index), "Duplicate search-index destinations"
    assert all(item.get("section") in SECTIONS for item in articles.values())
    expected_nav = {"/", *(f"/{section}/" for section in SECTIONS)}
    for path in ("/", *(f"/{section}/" for section in SECTIONS)):
        page = read_page(path)
        assert page.feed_nav_count == 1, f"{path}: missing or duplicate category navigation"
        assert len(page.feed_nav) == len(expected_nav) and set(page.feed_nav) == expected_nav
        assert page.feed_active == [path], f"{path}: current category is incorrect"
        assert page.feed_entry_count and page.feed_entries, f"{path}: empty article list"
        assert len(page.feed_entries) == len(set(page.feed_entries)), f"{path}: repeated articles"
        assert page.feed_summary_count == page.feed_entry_count, f"{path}: article summaries missing"
        assert page.entry_dates == sorted(page.entry_dates, reverse=True), f"{path}: articles out of date order"
        assert all(link in articles for link in page.feed_entries), f"{path}: unknown article destination"
        if path == "/":
            config = (ROOT.parent / "hugo.toml").read_text(encoding="utf-8")
            size = int(re.search(r"(?m)^\s*pagerSize\s*=\s*(\d+)", config).group(1))
            assert page.feed_entry_count == min(size, len(articles))
            cutoff = min(stamp(articles[link]) for link in page.feed_entries)
            newer = {link for link, item in articles.items() if stamp(item) > cutoff}
            assert newer.issubset(page.feed_entries), "Recent articles omitted from the unified feed"
        if path != "/":
            section = path.strip("/")
            assert all(articles[link]["section"] == section for link in page.feed_entries), f"{path}: mixed section entries"
            latest = max((item for item in articles.values() if item["section"] == section), key=stamp)
            assert page.entry_dates[0] == latest["date"][:10], f"{path}: latest publication date missing"
            latest_file = ROOT / route(latest["permalink"]).lstrip("/") / "index.html"
            assert latest_file.is_file(), f"Missing latest {section} article"
    cases = read_page("/cases/")
    assert cases.contact, "About page contact destination missing"
    case_cards = [link for link, contexts in cases.links if "article-list--compact" in contexts]
    assert not any(link.startswith("/hotspot-daily/") for link in case_cards), "Hotspot articles leaked into the about archive"
    print(f"Journal navigation passed: {len(articles)} indexed articles, 4 feeds and contact route")


if __name__ == "__main__":
    main()
