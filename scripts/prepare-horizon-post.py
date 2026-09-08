#!/usr/bin/env python3
"""Convert pinned Horizon Jekyll summaries into Hugo review drafts.

Only summaries with a clear law/compliance/privacy/cybersecurity signal are admitted.
Generated files remain drafts until a lawyer marks them verified and sets draft=false.
"""
from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

LEGAL_TERMS = {
    "法律", "律师", "法院", "司法", "判决", "监管", "合规", "隐私", "数据保护", "个人信息",
    "网络安全", "著作权", "版权", "知识产权", "侵权", "平台责任", "算法治理", "人工智能法",
    "ai regulation", "law", "legal", "court", "regulation", "compliance", "privacy",
    "data protection", "cybersecurity", "copyright", "intellectual property", "liability",
}


def strip_jekyll_front_matter(text: str) -> str:
    if not text.startswith("---"):
        return text.strip()
    parts = text.split("---", 2)
    return parts[2].strip() if len(parts) == 3 else text.strip()


def extract_title(body: str, fallback: str) -> str:
    for line in body.splitlines():
        line = line.strip()
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def is_relevant(text: str) -> bool:
    lower = text.lower()
    return any(term.lower() in lower for term in LEGAL_TERMS)


def toml_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def convert(src: Path, dest_dir: Path) -> Path | None:
    raw = src.read_text(encoding="utf-8")
    body = strip_jekyll_front_matter(raw)
    if not is_relevant(body):
        print(f"skip (not law/compliance focused): {src.name}")
        return None

    lang = "zh" if src.stem.endswith("-zh") else "en"
    title = extract_title(body, f"AI与法律合规观察 · {date.today().isoformat()}")
    if body.lstrip().startswith("# "):
        body = re.sub(r"^# .+?\n+", "", body, count=1)

    front = f'''+++
title = "{toml_escape(title)}"
date = "{date.today().isoformat()}T08:30:00+08:00"
draft = true
review_status = "pending"
reviewed_by = ""
last_verified = ""
categories = ["AI与法律"]
tags = ["人工智能", "法律合规"]
description = "AI、数据、隐私与平台治理相关法律动态的待审核资料稿。经律师核验后方公开发布。"
auto_generated = true
source_pipeline = "Horizon"
lang = "{lang}"
+++

> **审核状态：待律师核验。** 本文由自动情报流程生成，目前仅作为内部资料草稿，不对外发布。发布前须核验事实、法律依据、案例来源及表述边界。

'''
    dest_dir.mkdir(parents=True, exist_ok=True)
    out = dest_dir / src.name.replace("-summary-", "-ai-law-")
    out.write_text(front + body.strip() + "\n", encoding="utf-8")
    print(f"prepared draft: {out}")
    return out


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: prepare-horizon-post.py <horizon-post-dir> <hugo-dest-dir>")
        return 2
    src_dir = Path(sys.argv[1])
    dest_dir = Path(sys.argv[2])
    if not src_dir.exists():
        print(f"source directory not found: {src_dir}")
        return 0
    created = [convert(p, dest_dir) for p in sorted(src_dir.glob("*-summary-zh.md"))]
    print(f"created {sum(p is not None for p in created)} review draft(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
