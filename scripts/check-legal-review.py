#!/usr/bin/env python3
"""Fail CI when automated content is published without legal verification."""
from __future__ import annotations

import re
import sys
from pathlib import Path

POSTS = Path("content/posts")


def front_matter(text: str) -> str:
    text = text.lstrip("\ufeff")
    if text.startswith("+++"):
        parts = text.split("+++", 2)
        return parts[1] if len(parts) == 3 else ""
    if text.startswith("---"):
        parts = text.split("---", 2)
        return parts[1] if len(parts) == 3 else ""
    return ""


def value(fm: str, key: str) -> str:
    m = re.search(rf"(?mi)^\s*{re.escape(key)}\s*[:=]\s*[\"']?([^\"'\n#]+)", fm)
    return m.group(1).strip().lower() if m else ""


def truthy(v: str) -> bool:
    return v in {"true", "yes", "1"}


def main() -> int:
    errors: list[str] = []
    checked = 0
    for path in POSTS.rglob("*.md"):
        if path.name == "_index.md":
            continue
        fm = front_matter(path.read_text(encoding="utf-8", errors="replace"))
        if not fm:
            continue
        auto = truthy(value(fm, "auto_generated"))
        if not auto:
            continue
        checked += 1
        draft = value(fm, "draft")
        status = value(fm, "review_status")
        reviewer = value(fm, "reviewed_by")
        verified = value(fm, "last_verified")
        is_public = draft in {"", "false", "no", "0"}
        if is_public and status != "verified":
            errors.append(f"{path}: automated content cannot publish unless review_status=verified")
        if status == "verified" and (not reviewer or not verified):
            errors.append(f"{path}: verified content requires reviewed_by and last_verified")

    print(f"legal review gate checked {checked} automated article(s)")
    if errors:
        print("\n".join(f"ERROR: {e}" for e in errors))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
