# -*- coding: utf-8 -*-
"""Analyze saved HTML link structure with LinkExtractor."""

import sys
from pathlib import Path
from urllib.parse import urlparse

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT.parent))

from article_reader import LinkExtractor


FILES = {
    "The Economist": ("economist.html", "https://www.economist.com/latest"),
    "Project Syndicate": ("project_syndicate.html", "https://www.project-syndicate.org/"),
    "WSJ CN": ("wsj_cn.html", "https://cn.wsj.com/"),
}


for site_name, (filename, base_url) in FILES.items():
    print(f"\n{'=' * 60}")
    print(f"{site_name} ({filename})")
    print(f"{'=' * 60}")

    path = Path(filename)
    if not path.exists():
        print(f"missing: {path}")
        continue

    links = LinkExtractor().extract(
        path.read_text(encoding="utf-8"),
        base_url,
        same_domain=False,
        min_title_length=1,
    )
    print(f"links: {len(links)}")

    path_patterns = {}
    article_like_links = []
    for link in links:
        parsed = urlparse(link.url)
        parts = [part for part in parsed.path.split("/") if part]
        if parts:
            pattern = f"/{'/'.join(parts[:2])}" if len(parts) >= 2 else f"/{parts[0]}"
            path_patterns[pattern] = path_patterns.get(pattern, 0) + 1
        if len(link.title) > 20 and len(parts) >= 2:
            article_like_links.append(link)

    print("\npath patterns top 15:")
    for pattern, count in sorted(path_patterns.items(), key=lambda item: -item[1])[:15]:
        print(f"  {pattern}: {count}")

    print("\narticle-like samples:")
    for link in article_like_links[:15]:
        print(f"  {urlparse(link.url).path}")
        print(f"    {link.title[:80]}")
