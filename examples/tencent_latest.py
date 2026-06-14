# -*- coding: utf-8 -*-
"""Extract article links and details from Tencent News."""

import asyncio

from path_setup import add_src_to_path

add_src_to_path()

from web_scraper import SmartFetcher


LIST_URL = "https://news.qq.com/"


async def main() -> None:
    async with SmartFetcher() as fetcher:
        links = await fetcher.fetch_links(
            LIST_URL,
            include_domains=["news.qq.com", "new.qq.com"],
            min_title_length=6,
        )

        print(f"links: {len(links)}")
        for link in links[:10]:
            print(f"- {link.title} ({link.url})")

        for link in links[:3]:
            article = await fetcher.fetch(link.url)
            print()
            print(article.title or link.title)
            print(f"success={article.success} length={article.length} method={article.method}")
            if article.content:
                print(article.content[:500].replace("\n", " "))


if __name__ == "__main__":
    asyncio.run(main())
