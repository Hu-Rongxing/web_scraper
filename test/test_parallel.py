# -*- coding: utf-8 -*-
"""Test: 多站点并行抓取 (pool_size=3, 多 URL 并发)

验证 pool_size > 1 的并行能力:
  - CloakBrowser 每个 slot 独立 user_data_dir
  - 3 个 slot 可同时抓取 3 个不同网站
"""

import sys
import asyncio
import time
from path_setup import add_src_to_path
add_src_to_path()

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from web_scraper import SmartFetcher

# 测试 URL: 来自上次的成功链接 (WSJ/Economist 各选 3 个, 已确认有效)
TEST_URLS = [
    "https://www.wsj.com/market-data/quotes/index/US/DJIA",
    "https://www.wsj.com/market-data/quotes/index/US/SPX",
    "https://www.wsj.com/market-data/quotes/index/US/COMP",
    "https://www.economist.com/leaders/2026/06/10/the-world-cup-paradox",
    "https://www.economist.com/leaders/2026/06/10/donald-trumps-least-bad-option-in-iran",
    "https://www.economist.com/leaders/2026/06/11/for-its-own-sake-china-should-change-its-growth-model",
    # Tencent (PageFetcher, 不占浏览器)
    "https://news.qq.com/rain/a/20260612A07LQF00",
    "https://news.qq.com/rain/a/20260612A03I7I00",
    "https://news.qq.com/rain/a/20260612A05GWC00",
]


async def test_sequential(f):
    """串行: 逐个抓取 9 个 URL."""
    print("\n--- 串行模式 (sequential) ---")
    t0 = time.time()
    results = []
    for i, url in enumerate(TEST_URLS, 1):
        t1 = time.time()
        r = await f.fetch(url)
        elapsed = time.time() - t1
        results.append((r, elapsed))
        status = "OK" if r.success else "FAIL"
        print(f"  [{i}] {elapsed:5.1f}s {status} {r.length:>6,} chars  engine={r.method}")
    total = time.time() - t0
    ok = sum(1 for r, _ in results if r.success)
    print(f"  Result: {ok}/{len(results)} success, total={total:.1f}s, avg={total/len(results):.1f}s")
    return total


async def test_parallel(f, concurrency: int = 3):
    """并行: 用信号量控制最大并发数."""
    from asyncio import Semaphore
    sem = Semaphore(concurrency)

    async def _fetch_one(i, url):
        async with sem:
            t1 = time.time()
            r = await f.fetch(url)
            elapsed = time.time() - t1
            status = "OK" if r.success else "FAIL"
            print(f"  [{i}] {elapsed:5.1f}s {status} {r.length:>6,} chars  engine={r.method}")
            return r, elapsed

    print(f"\n--- 并行模式 (parallel, concurrency={concurrency}) ---")
    t0 = time.time()
    tasks = [_fetch_one(i, url) for i, url in enumerate(TEST_URLS, 1)]
    results = await asyncio.gather(*tasks)
    total = time.time() - t0
    ok = sum(1 for r, _ in results if r.success)
    print(f"  Result: {ok}/{len(results)} success, total={total:.1f}s, avg={total/len(results):.1f}s")
    return total


async def test_single_pool_parallel():
    """单池并行: 1 个 BrowserPool size=3, 3 个并发 slot."""
    print("=" * 70)
    print("Test: Single BrowserPool (size=3), parallel fetches")
    print("=" * 70)

    f = SmartFetcher(pool_size=3, preload=True, keep_alive=True)
    await f.start()
    seq_time = await test_sequential(f)
    par_time = await test_parallel(f, concurrency=3)
    speedup = seq_time / par_time if par_time > 0 else 0
    print(f"\n  ⚡ 串行 {seq_time:.1f}s → 并行 {par_time:.1f}s, 加速比 {speedup:.1f}x")
    await f.shutdown()


async def test_wsj_concurrent():
    """WSJ 并发: 3 篇 WSJ 同时抓取."""
    WSJ_URLS = [
        "https://www.wsj.com/market-data/quotes/index/US/DJIA",
        "https://www.wsj.com/market-data/quotes/index/US/SPX",
        "https://www.wsj.com/market-data/quotes/index/US/COMP",
    ]

    print("\n" + "=" * 70)
    print("Test: 3 WSJ articles in parallel (pool_size=3)")
    print("=" * 70)

    f = SmartFetcher(pool_size=3, preload=True, keep_alive=True)
    await f.start()

    t0 = time.time()
    tasks = [f.fetch(url) for url in WSJ_URLS]
    results = await asyncio.gather(*tasks)
    total = time.time() - t0

    for i, r in enumerate(results, 1):
        print(f"  [WSJ #{i}] {r.title[:50] if r.title else 'N/A'}")
        print(f"         {r.length:,} chars  engine={r.method}")
    print(f"  Result: {total:.1f}s total (vs ~60s sequential)")
    await f.shutdown()


async def main():
    await test_single_pool_parallel()
    await test_wsj_concurrent()


if __name__ == "__main__":
    asyncio.run(main())
