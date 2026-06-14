# -*- coding: utf-8 -*-
"""Smoke-test list links and one article for four target sites."""

import asyncio
import os
import re
import sys
from path_setup import add_src_to_path
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
add_src_to_path()

from web_scraper import SmartFetcher


SITES = {
    "The Economist": {
        "list_url": "https://www.economist.com/latest",
        "domain": "economist.com",
        "article_patterns": [
            r"economist\.com/\w+/[\w-]+$",
            r"economist\.com/[\w-]+/[\w-]+$",
        ],
        "exclude_paths": [
            "/pro",
            "/subscribe",
            "/login",
            "/account",
            "/print",
            "/podcasts",
            "/videos",
            "/the-world-in-brief",
            "/game",
            "/jobs",
            "/store",
        ],
        "exclude_keywords": ["subscribe", "newsletter", "sign in", "log in"],
    },
    "MarketWatch": {
        "list_url": "https://www.marketwatch.com/latest-news",
        "domain": "marketwatch.com",
        "article_patterns": [
            r"marketwatch\.com/story/[\w-]+",
            r"marketwatch\.com/articles/[\w-]+",
        ],
        "exclude_paths": ["/tools", "/games", "/watchlist", "/investing", "/markets"],
        "exclude_keywords": ["subscribe", "newsletter", "sign in", "video", "podcast"],
    },
    "Project Syndicate": {
        "list_url": "https://www.project-syndicate.org/",
        "domain": "project-syndicate.org",
        "article_patterns": [
            r"project-syndicate\.org/(?:commentary|magazine|interviews|longreads)/[\w-]+-\d{4}-\d{2}$",
        ],
        "exclude_paths": ["/about", "/contact", "/subscribe", "/login", "/search", "/topics"],
        "exclude_keywords": ["subscribe", "newsletter", "about", "contact", "search"],
    },
    "WSJ CN": {
        "list_url": "https://cn.wsj.com/",
        "domain": "wsj.com",
        "article_patterns": [r"wsj\.com/articles/", r"wsj\.com/zh-hans/news/"],
        "exclude_paths": ["/subscribe", "/login", "/video", "/podcasts", "/search"],
        "exclude_keywords": ["subscribe", "newsletter", "login", "signin", "video"],
    },
}


def is_article_url(url: str, config: dict) -> bool:
    path = url.split("?", 1)[0].lower()
    if any(excluded in path for excluded in config.get("exclude_paths", [])):
        return False
    if any(keyword in url.lower() for keyword in config.get("exclude_keywords", [])):
        return False
    return any(re.search(pattern, url) for pattern in config.get("article_patterns", []))


def filter_article_links(raw_links, site_name: str) -> list[dict]:
    config = SITES[site_name]
    links = []
    seen = set()
    for link in raw_links:
        if link.url in seen or not is_article_url(link.url, config):
            continue
        title = link.title.strip()
        if 15 <= len(title) <= 200:
            seen.add(link.url)
            links.append({"url": link.url, "title": title[:120]})
    return links


async def test_site(fetcher: SmartFetcher, site_name: str):
    config = SITES[site_name]
    print(f"\n{'=' * 60}")
    print(f"{site_name}: {config['list_url']}")

    t0 = time.monotonic()
    raw_links = await fetcher.fetch_links(
        config["list_url"],
        same_domain=False,
        include_domains=[config["domain"]],
        min_title_length=1,
        max_title_length=200,
    )
    elapsed = (time.monotonic() - t0) * 1000
    links = filter_article_links(raw_links, site_name)

    print(f"list links: raw={len(raw_links)} article={len(links)} elapsed={elapsed:.0f}ms")
    for index, link in enumerate(links[:10], 1):
        print(f"  [{index}] {link['title'][:55]}")
        print(f"      {link['url'][:90]}")

    if not links:
        return {"list_ok": True, "links_count": 0, "links": [], "article": None}

    chosen = links[0]
    t1 = time.monotonic()
    article_result = await fetcher.fetch(chosen["url"])
    article_elapsed = (time.monotonic() - t1) * 1000

    print(
        f"article: success={article_result.success} "
        f"pipeline=P{article_result.meta.get('pipeline_level', '?')} "
        f"elapsed={article_elapsed:.0f}ms length={len(article_result.content or '')}"
    )

    return {
        "list_ok": True,
        "links_count": len(links),
        "links": links[:5],
        "article": {
            "success": article_result.success,
            "title": article_result.title,
            "author": article_result.author,
            "date": article_result.date,
            "content_length": len(article_result.content or ""),
            "pipeline": article_result.meta.get("pipeline_level"),
            "elapsed_ms": article_elapsed,
            "error": article_result.error,
        },
    }


async def main():
    results = {}
    async with SmartFetcher() as fetcher:
        for site_name in SITES:
            results[site_name] = await test_site(fetcher, site_name)

    print(f"\n{'=' * 70}")
    print("summary")
    for site_name, result in results.items():
        article = result.get("article")
        article_status = "not-tested"
        if article:
            article_status = "ok" if article.get("success") else (article.get("error") or "failed")[:60]
        print(f"{site_name}: links={result.get('links_count', 0)} article={article_status}")


if __name__ == "__main__":
    asyncio.run(main())
