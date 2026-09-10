#!/usr/bin/env python3
"""Validate public/legal-content-gaps.json after build."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FEED = ROOT / "public" / "legal-content-gaps.json"
INTENTS = ROOT / "data" / "legal-search-intents.json"
TOPICS = ROOT / "data" / "legal-topic-entities.json"


def load(path: Path):
    if not path.exists():
        raise SystemExit(f"content gap check: missing {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    feed = load(FEED)
    intents = load(INTENTS)
    topics = load(TOPICS)

    known_intents = {item.get("id") for item in intents.get("intents", [])}
    known_topics = {item.get("id") for item in topics.get("topics", [])}
    known_areas = {item.get("id") for item in topics.get("practiceAreas", [])}

    gaps = feed.get("gaps", [])
    seen = set()
    failures = []
    for gap in gaps:
        gap_id = gap.get("id")
        if gap_id in seen:
            failures.append(f"duplicate gap id: {gap_id}")
        seen.add(gap_id)
        if gap_id not in known_intents:
            failures.append(f"unknown intent id: {gap_id}")
        topic_id = (gap.get("parentTopic") or {}).get("id")
        area_id = (gap.get("practiceArea") or {}).get("id")
        if topic_id not in known_topics:
            failures.append(f"unknown topic id for {gap_id}: {topic_id}")
        if area_id not in known_areas:
            failures.append(f"unknown practice area for {gap_id}: {area_id}")
        score = gap.get("priorityScore")
        if not isinstance(score, int) or not 0 <= score <= 100:
            failures.append(f"invalid priority score for {gap_id}: {score}")
        if not gap.get("searchIntent") or not gap.get("recommendedTitle"):
            failures.append(f"missing intent/title for {gap_id}")

    stats = feed.get("stats", {})
    if stats.get("openGaps") != len(gaps):
        failures.append("stats.openGaps does not equal gaps length")
    if len(gaps) > len(known_intents):
        failures.append("gap count exceeds configured intent count")

    if failures:
        print("Content gap validation failed:")
        for item in failures:
            print("-", item)
        return 1

    print(f"Content gap validation passed: {len(gaps)} gap(s), {len(known_intents)} configured intent(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
