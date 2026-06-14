# -*- coding: utf-8 -*-
"""抓取经济学人指定文章全文."""
import sys
import asyncio
from path_setup import add_src_to_path
add_src_to_path()

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from article_reader import SmartFetcher

async def main():
    url = "https://www.economist.com/leaders/2026/06/10/donald-trumps-least-bad-option-in-iran"
    async with SmartFetcher() as f:
        print(f"抓取: {url}\n")
        r = await f.fetch(url)
        if r.success:
            print(f"标题: {r.title}")
            print(f"日期: {r.date}")
            print("栏目: Leaders | Dire strait")
            print(f"长度: {r.length:,} chars")
            print(f"方法: {r.method}")
            print(f"{'='*70}")
            print(r.content)
        else:
            print(f"失败: {r.error}")

asyncio.run(main())
