# -*- coding: utf-8 -*-
"""Debug list-page link extraction through SmartFetcher.fetch_links."""

import asyncio
import os
import re
import sys
from path_setup import add_src_to_path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
add_src_to_path()

from web_scraper import SmartFetcher


async def debug_links(fetcher, url, site_name, domain, sample_paths=None):
    print(f"\n{'=' * 60}")
    print(f"{site_name}: {url}")
    print(f"{'=' * 60}")

    links = await fetcher.fetch_links(
        url,
        same_domain=False,
        include_domains=[domain],
        min_title_length=1,
        max_title_length=200,
    )
    print(f"  Links: {len(links)}")

    with_text = [link for link in links if len(link.title) > 10]
    print(f"  Links with text >10 chars: {len(with_text)}")

    for i, link in enumerate(with_text[:30]):
        print(f"    [{i + 1}] text={link.title[:50]}")
        print(f"         url={link.url[:90]}")

    if sample_paths:
        print("\n  Matches:")
        for link in links:
            for pattern in sample_paths:
                if re.search(pattern, link.url):
                    print(f"    OK {link.title[:50]}")
                    print(f"       {link.url[:90]}")
                    break


async def main():
    async with SmartFetcher() as fetcher:
        await debug_links(
            fetcher,
            "https://www.economist.com/latest",
            "The Economist",
            "economist.com",
            sample_paths=[r"/\w+/[\w-]+$", r"/article/"],
        )
        await debug_links(
            fetcher,
            "https://www.project-syndicate.org/",
            "Project Syndicate",
            "project-syndicate.org",
            sample_paths=[r"/articles?/", r"/\w+/[\w-]+$"],
        )
        await debug_links(
            fetcher,
            "https://cn.wsj.com/",
            "WSJ CN",
            "cn.wsj.com",
            sample_paths=[r"/articles/"],
        )


if __name__ == "__main__":
    asyncio.run(main())
