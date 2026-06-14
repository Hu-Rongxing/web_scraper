# -*- coding: utf-8 -*-
"""Analyze saved Economist HTML links with LinkExtractor."""

import re
import sys
from pathlib import Path
from path_setup import add_src_to_path
from urllib.parse import urlparse

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
add_src_to_path()

from web_scraper import LinkExtractor


html_path = Path(r"D:\oc_workspace\main\web_scraper\test\economist_latest.html")
if not html_path.exists():
    print(f"missing: {html_path}")
    sys.exit(1)

html = html_path.read_text(encoding="utf-8")
print(f"html length: {len(html)}")

links = LinkExtractor().extract(
    html,
    "https://www.economist.com/latest",
    same_domain=False,
    include_domains=["economist.com"],
    min_title_length=1,
)
print(f"economist.com links: {len(links)}")

path_patterns = {}
for link in links:
    path = urlparse(link.url).path
    parts = path.strip("/").split("/")
    if parts and parts[0]:
        path_patterns[parts[0]] = path_patterns.get(parts[0], 0) + 1

print("\npath patterns:")
for pattern, count in sorted(path_patterns.items(), key=lambda item: -item[1])[:20]:
    print(f"  /{pattern}/... : {count}")

print("\narticle-like samples:")
article_links = [
    link
    for link in links
    if re.search(r"/\w+/[\w-]+$", urlparse(link.url).path) and len(link.title) > 20
]
for link in article_links[:10]:
    print(f"  {urlparse(link.url).path}")
    print(f"    {link.title[:100]}")
