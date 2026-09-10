#!/usr/bin/env python3
"""Check internal links after Hugo + VuePress have produced public/.

This is intentionally conservative: only site-root links are checked. External
URLs, mail/tel/javascript links, fragments and data URLs are ignored.
"""

from __future__ import annotations

import html
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"
HREF_RE = re.compile(r'''(?i)\bhref\s*=\s*["']([^"']+)["']''')
IGNORE_PREFIXES = ("http://", "https://", "mailto:", "tel:", "javascript:", "data:", "//")


def target_exists(url_path: str) -> bool:
    path = unquote(url_path)
    if not path.startswith("/"):
        return True
    rel = path.lstrip("/")
    if not rel:
        return (PUBLIC / "index.html").exists()

    candidate = PUBLIC / rel
    if candidate.is_file():
        return True
    if candidate.is_dir() and (candidate / "index.html").is_file():
        return True
    if candidate.suffix:
        return False
    return (candidate / "index.html").is_file() or candidate.with_suffix(".html").is_file()


def main() -> int:
    if not PUBLIC.exists():
        print("ERROR: public/ does not exist; run build.sh first.", file=sys.stderr)
        return 1

    broken: dict[tuple[str, str], None] = {}
    checked = 0

    for page in PUBLIC.rglob("*.html"):
        text = page.read_text(encoding="utf-8", errors="ignore")
        for raw_href in HREF_RE.findall(text):
            href = html.unescape(raw_href.strip())
            if not href or href.startswith("#") or href.startswith(IGNORE_PREFIXES):
                continue
            parsed = urlsplit(href)
            if parsed.scheme or parsed.netloc or not parsed.path.startswith("/"):
                continue
            checked += 1
            if not target_exists(parsed.path):
                source = "/" + page.relative_to(PUBLIC).as_posix()
                broken[(source, href)] = None

    if broken:
        for source, href in sorted(broken):
            print(f"ERROR: broken internal link: {source} -> {href}", file=sys.stderr)
        print(f"Built-link check failed: {len(broken)} unique broken link(s).", file=sys.stderr)
        return 1

    print(f"Built-link check passed: {checked} internal link occurrence(s) checked.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
