# -*- coding: utf-8 -*-
"""
SmartFetcher 集成测试

用法:
  python test_smart.py                          # 测试自动路由
  python test_smart.py --url <url>              # 测试指定 URL
  python test_smart.py --force dynamic --url <url>  # 强制 engine
  python test_smart.py --list                   # 列出支持的站点
"""

import sys
import asyncio
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from article_reader import SmartFetcher, FetchResult


async def main():
    if "--list" in sys.argv:
        async with SmartFetcher() as fetcher:
            sites = fetcher.supported_sites
            print(f"\nBPC 支持站点: {len(sites)}")

            query = None
            for i, arg in enumerate(sys.argv[1:]):
                if arg == "--list" and i + 1 < len(sys.argv):
                    query = sys.argv[i + 1]
                    break

            if query:
                sites = [s for s in sites if query.lower() in s]
                print(f"搜索 '{query}': {len(sites)} 匹配")
            for s in sites[:100]:
                print(f"  {s}")
            if len(sites) > 100:
                print(f"  ... 还有 {len(sites) - 100} 个")
        return

    # ---- 测试 URL ----
    test_urls = []

    # 检查是否命令行传了 URL
    for i, arg in enumerate(sys.argv[1:]):
        if arg.startswith("http"):
            test_urls.append(arg)

    if not test_urls:
        # 默认测试集: 3 种类型
        test_urls = [
            # Article (付费)
            "https://www.wsj.com/articles/suspected-sabotage-of-deep-sea-cable-triggers-first-nato-led-response-337119ba",
            # Page (通用网页)
            "https://example.com",
        ]

    force = None
    for i, arg in enumerate(sys.argv[1:]):
        if arg == "--force" and i + 1 < len(sys.argv):
            force = sys.argv[i + 1]
            break

    print("=" * 70)
    print("SmartFetcher 集成测试")
    print(f"  URLs: {len(test_urls)}")
    print(f"  Force: {force or 'auto'}")
    print("=" * 70)

    t_total = time.monotonic()

    async with SmartFetcher() as fetcher:
        for url in test_urls:
            print(f"\n>>> {url}")
            t0 = time.monotonic()
            result = await fetcher.fetch(url, force=force)
            dt = time.monotonic() - t0

            print(f"    类型: {result.content_type}")
            print(f"    方法: {result.method}")
            print(f"    标题: {result.title[:80] if result.title else '(none)'}")
            print(f"    长度: {result.length:,} 字符")
            print(f"    成功: {result.success}")
            print(f"    耗时: {dt:.1f}s ({result.elapsed_ms:.0f}ms)")
            if result.error:
                print(f"    错误: {result.error}")
            if result.content:
                preview = result.content[:300].replace("\n", "\n    ")
                print(f"    预览:\n    {preview}")

        print(f"\n{'=' * 70}")
        print(f"总耗时: {time.monotonic() - t_total:.1f}s")
        print(f"状态:\n  {fetcher.stats()}")
        print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
