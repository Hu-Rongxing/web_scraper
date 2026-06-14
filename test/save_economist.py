# -*- coding: utf-8 -*-
"""Save rendered Economist HTML for local analysis."""

import asyncio
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

from article_reader import SmartFetcher


async def main():
    async with SmartFetcher() as fetcher:
        result = await fetcher.fetch("https://www.economist.com/latest")
        if result.html:
            output_path = r"D:\oc_workspace\main\article_reader\test\economist_latest.html"
            with open(output_path, "w", encoding="utf-8") as file:
                file.write(result.html)
            print(f"saved: {output_path} ({len(result.html)} chars)")
        else:
            print(f"failed: {result.error}")


if __name__ == "__main__":
    asyncio.run(main())
