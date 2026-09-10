#!/usr/bin/env python3
"""Generate prioritized legal content gaps from the search-intent graph.

Outputs:
- public/legal-content-gaps.json       stable machine-readable feed for tasks
- build-reports/legal-content-gap-report.md  human-readable build report

This script does not alter visible page HTML or CSS.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"
REPORT_DIR = ROOT / "build-reports"
INTENT_GRAPH = PUBLIC / "legal-intent-graph.json"
TOPIC_GRAPH = PUBLIC / "legal-topic-graph.json"
CONFIG = ROOT / "data" / "content-gap-priorities.json"
OUTPUT = PUBLIC / "legal-content-gaps.json"
REPORT = REPORT_DIR / "legal-content-gap-report.md"


def load(path: Path):
    if not path.exists():
        raise SystemExit(f"content gap: required file missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def main() -> int:
    intent_graph = load(INTENT_GRAPH)
    topic_graph = load(TOPIC_GRAPH)
    config = load(CONFIG)

    intent_nodes = intent_graph.get("nodes", {}).get("intents", [])
    topic_nodes = topic_graph.get("nodes", {}).get("topics", [])
    area_nodes = topic_graph.get("nodes", {}).get("practiceAreas", [])
    topic_edges = topic_graph.get("edges", [])

    topic_by_id = {item.get("id"): item for item in topic_nodes if isinstance(item, dict) and item.get("id")}
    area_by_id = {item.get("id"): item for item in area_nodes if isinstance(item, dict) and item.get("id")}

    topic_laws: dict[str, list[str]] = {}
    for edge in topic_edges:
        if not isinstance(edge, dict) or edge.get("type") != "aggregatesLaw":
            continue
        topic_laws.setdefault(edge.get("from"), []).append(edge.get("to"))

    law_nodes = topic_graph.get("nodes", {}).get("laws", [])
    law_by_id = {item.get("id"): item for item in law_nodes if isinstance(item, dict) and item.get("id")}

    practice_weights = config.get("practiceAreaWeights", {})
    intent_weights = config.get("intentTypeWeights", {})
    base = int(config.get("baseScore", 35))
    scarcity_max = int(config.get("topicScarcityMax", 18))
    law_bonus = int(config.get("lawSupportBonus", 10))
    max_score = int(config.get("maxScore", 100))

    gaps = []
    for intent in intent_nodes:
        if not isinstance(intent, dict):
            continue
        article_count = int(intent.get("articleCount") or 0)
        if article_count > 0:
            continue

        intent_id = intent.get("id")
        parent_topic = intent.get("parentTopic")
        topic = topic_by_id.get(parent_topic)
        if not intent_id or not topic:
            raise SystemExit(f"content gap: missing intent id or unknown parent topic: {intent}")

        practice_area = topic.get("practiceArea")
        area = area_by_id.get(practice_area)
        if not practice_area or not area:
            raise SystemExit(f"content gap: unknown practice area for topic {parent_topic}")

        topic_article_count = int(topic.get("articleCount") or 0)
        scarcity = clamp(scarcity_max - min(topic_article_count // 8, scarcity_max), 0, scarcity_max)
        practice_score = int(practice_weights.get(practice_area, 0))
        intent_score = int(intent_weights.get(intent.get("intentType"), 0))

        related_laws = []
        for law_id in sorted(set(topic_laws.get(parent_topic, []))):
            law = law_by_id.get(law_id)
            if law:
                related_laws.append({"id": law_id, "title": law.get("title"), "url": law.get("url")})

        law_support = law_bonus if related_laws else 0
        score = clamp(base + practice_score + intent_score + scarcity + law_support, 0, max_score)

        name = (intent.get("name") or "").strip()
        gaps.append({
            "id": intent_id,
            "searchIntent": name,
            "intentType": intent.get("intentType"),
            "parentTopic": {"id": parent_topic, "name": topic.get("name")},
            "practiceArea": {"id": practice_area, "name": area.get("name")},
            "priorityScore": score,
            "scoreBreakdown": {
                "base": base,
                "practiceArea": practice_score,
                "intentType": intent_score,
                "topicScarcity": scarcity,
                "confirmedLawSupport": law_support
            },
            "recommendedTitle": name,
            "suggestedLaws": related_laws,
            "reason": "当前搜索意图没有已匹配文章，建议优先补齐。"
        })

    gaps.sort(key=lambda item: (-item["priorityScore"], item["searchIntent"]))

    payload = {
        "version": 1,
        "generatedBy": "caoyide-blog/scripts/build-legal-content-gaps.py",
        "feedUrl": "https://caoyide.com/legal-content-gaps.json",
        "selectionRule": "优先从高分缺口中选题，再结合当天热点、事实可核验性与律师专业相关性决定是否生产。",
        "stats": {
            "configuredIntents": len(intent_nodes),
            "openGaps": len(gaps),
            "highPriorityGaps": sum(1 for item in gaps if item["priorityScore"] >= 80)
        },
        "gaps": gaps
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    lines = [
        "# 法律内容缺口报告",
        "",
        f"- 搜索意图总数：{len(intent_nodes)}",
        f"- 当前未覆盖：{len(gaps)}",
        f"- 80分以上高优先级：{payload['stats']['highPriorityGaps']}",
        "",
        "| 优先级 | 搜索意图 | 专业领域 | 上级主题 | 已确认法律支撑 |",
        "|---:|---|---|---|---|",
    ]
    for gap in gaps:
        laws = "、".join(law.get("title") or law.get("id") for law in gap["suggestedLaws"]) or "暂无"
        lines.append(f"| {gap['priorityScore']} | {gap['searchIntent']} | {gap['practiceArea']['name']} | {gap['parentTopic']['name']} | {laws} |")
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Content gap feed complete: {len(gaps)} open gap(s), {payload['stats']['highPriorityGaps']} high-priority gap(s).")
    print(f"Feed: {OUTPUT}")
    print(f"Report: {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
