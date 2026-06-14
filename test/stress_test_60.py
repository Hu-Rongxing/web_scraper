# -*- coding: utf-8 -*-
"""60-site stress test: 验证 pool_size>1 并行抓取

从 BPC 939 域名 + 已知有效站点中各选一批,
用 SmartFetcher (pool_size=3) 并发抓取.

策略:
  - 10 个 BPC 站点 (WSJ/Bloomberg/FT/NYT 等) → ArticleFetcher
  - 10 个非 BPC 站点 (Tencent 等) → PageFetcher / DynamicFetcher
  - 40 个已知快速站点 (httpbin/github/example 等) → PageFetcher
  - 用信号量 concurrency=5 控制
"""

import sys, asyncio, time, random
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from article_reader import SmartFetcher

# ---- Test URLs ----

# 10 BPC news sites (confirmed working or high-confidence)
BPC_URLS = [
    "https://www.wsj.com/market-data/quotes/index/US/DJIA",
    "https://www.wsj.com/market-data/quotes/index/US/SPX",
    "https://www.economist.com/leaders/2026/06/10/the-world-cup-paradox",
    "https://www.economist.com/leaders/2026/06/10/donald-trumps-least-bad-option-in-iran",
    "https://www.economist.com/leaders/2026/06/11/for-its-own-sake-china-should-change-its-growth-model",
    "https://www.bloomberg.com/markets",
    "https://www.ft.com/",
    "https://www.nytimes.com/",
    "https://www.theguardian.com/international",
    "https://www.washingtonpost.com/",
]

# 10 non-BPC / Chinese sites → PageFetcher or DynamicFetcher
CHINESE_URLS = [
    "https://news.qq.com/rain/a/20260612A07LQF00",
    "https://news.qq.com/rain/a/20260612A03I7I00",
    "https://news.qq.com/rain/a/20260612A05GWC00",
    "https://www.baidu.com/",
    "https://www.zhihu.com/",
    "https://www.douban.com/",
    "https://weibo.com/",
    "https://www.bilibili.com/",
    "https://www.toutiao.com/",
    "https://www.sina.com.cn/",
]

# 40 fast static sites → PageFetcher (no browser)
FAST_URLS = [
    "https://httpbin.org/get",
    "https://httpbin.org/html",
    "https://httpbin.org/links/10/0",
    "https://example.com/",
    "https://example.org/",
    "https://example.net/",
    "https://www.google.com/",
    "https://www.bing.com/",
    "https://www.yahoo.com/",
    "https://www.wikipedia.org/",
    "https://github.com/",
    "https://stackoverflow.com/",
    "https://www.python.org/",
    "https://news.ycombinator.com/",
    "https://www.reddit.com/",
    "https://www.apple.com/",
    "https://www.microsoft.com/",
    "https://www.amazon.com/",
    "https://www.netflix.com/",
    "https://www.spotify.com/",
    "https://www.dropbox.com/",
    "https://www.notion.so/",
    "https://www.figma.com/",
    "https://www.shopify.com/",
    "https://www.stripe.com/",
    "https://www.cloudflare.com/",
    "https://www.vercel.com/",
    "https://www.twitch.tv/",
    "https://www.medium.com/",
    "https://www.quora.com/",
    "https://www.bbc.com/",
    "https://www.cnn.com/",
    "https://www.reuters.com/",
    "https://www.aljazeera.com/",
    "https://www.nature.com/",
    "https://www.npmjs.com/",
    "https://pypi.org/",
    "https://www.npmjs.com/package/react",
    "https://www.typescriptlang.org/",
    "https://developer.mozilla.org/en-US/",
]


async def run_stress_test(urls: list[str], label: str, f: SmartFetcher,
                          concurrency: int = 5):
    """并发抓取, 打印结果."""
    from asyncio import Semaphore
    sem = Semaphore(concurrency)
    results = []
    t0 = time.time()

    async def _fetch(i, url):
        t1 = time.time()
        async with sem:
            try:
                r = await f.fetch(url)
                elapsed = time.time() - t1
                status = "OK" if r.success else "FAIL"
                engine = getattr(r, 'method', '?')
                results.append({
                    "url": url, "success": r.success, "chars": r.length,
                    "elapsed": elapsed, "engine": engine,
                    "error": getattr(r, 'error', None),
                })
                title = (getattr(r, 'title', '') or '')[:40]
                print(f"  [{i:2d}] {elapsed:5.1f}s {status:4s}  {r.length:>6,} chars  {engine:25s}  {title}")
            except Exception as e:
                elapsed = time.time() - t1
                results.append({
                    "url": url, "success": False, "chars": 0,
                    "elapsed": elapsed, "engine": "error",
                    "error": str(e)[:100],
                })
                print(f"  [{i:2d}] {elapsed:5.1f}s ERROR  {str(e)[:60]}")

    print(f"\n{'='*80}")
    print(f"  {label}: {len(urls)} URLs, concurrency={concurrency}")
    print(f"{'='*80}")

    tasks = [_fetch(i, url) for i, url in enumerate(urls, 1)]
    await asyncio.gather(*tasks)
    total = time.time() - t0

    ok = sum(1 for r in results if r["success"])
    chars = sum(r["chars"] for r in results)
    avg = sum(r["elapsed"] for r in results) / len(results) if results else 0
    browser_ok = sum(1 for r in results if r["success"] and "article" in r["engine"])
    page_ok = sum(1 for r in results if r["success"] and "page" in r["engine"])

    print(f"  ── Result: {ok}/{len(results)} OK | {chars:,} chars | avg={avg:.1f}s | total={total:.1f}s")
    print(f"  ── Breakdown: {page_ok} via PageFetcher, {browser_ok} via ArticleFetcher")
    print()
    return results, total


async def main():
    print("=" * 80)
    print("  60-Site Stress Test — Article Reader with Shared BrowserPool (size=3)")
    print("=" * 80)

    # 单一 SmartFetcher 实例
    f = SmartFetcher(pool_size=3, preload=True, keep_alive=True)
    t_startup = time.time()
    await f.start()
    print(f"  SmartFetcher ready in {time.time()-t_startup:.1f}s\n")

    grand_total_start = time.time()
    all_results = []

    # Phase 1: 10 BPC news sites (ArticleFetcher, uses CloakBrowser)
    r1, t1 = await run_stress_test(BPC_URLS, "Phase 1: BPC News Sites (ArticleFetcher)", f, concurrency=3)
    all_results.extend(r1)

    # Phase 2: 10 Chinese / non-BPC sites (SmartFetcher auto-routing)
    r2, t2 = await run_stress_test(CHINESE_URLS, "Phase 2: Chinese/Non-BPC Sites (Auto-route)", f, concurrency=5)
    all_results.extend(r2)

    # Phase 3: 40 fast static sites (PageFetcher, no browser)
    r3, t3 = await run_stress_test(FAST_URLS, "Phase 3: 40 Fast Static Sites (PageFetcher)", f, concurrency=10)
    all_results.extend(r3)

    await f.shutdown()
    grand_total = time.time() - grand_total_start

    # ---- Final Report ----
    print("=" * 80)
    print("  FINAL REPORT")
    print("=" * 80)

    ok = sum(1 for r in all_results if r["success"])
    total_chars = sum(r["chars"] for r in all_results)
    times = [r["elapsed"] for r in all_results]

    engines = {}
    for r in all_results:
        eng = r["engine"] or "unknown"
        engines[eng] = engines.get(eng, 0) + 1

    print(f"\n  Total URLs:     {len(all_results)}")
    print(f"  Success:        {ok}/{len(all_results)}")
    print(f"  Total chars:    {total_chars:,}")
    print(f"  Grand total:    {grand_total:.1f}s")
    if times:
        avg = sum(times) / len(times)
        sorted_t = sorted(times)
        p50 = sorted_t[len(sorted_t)//2]
        p90 = sorted_t[int(len(sorted_t)*0.9)]
        print(f"  Avg/time:       {avg:.1f}s")
        print(f"  Range:          {min(times):.1f}s ~ {max(times):.1f}s")
        print(f"  p50:            {p50:.1f}s")
        print(f"  p90:            {p90:.1f}s")

    print(f"\n  Engine breakdown:")
    for eng, cnt in sorted(engines.items()):
        print(f"    {eng}: {cnt}")

    # 分段时间
    print(f"\n  Phase timing:")
    print(f"    BPC news (10):       {t1:.1f}s")
    print(f"    Chinese/non-BPC (10): {t2:.1f}s")
    print(f"    Fast static (40):     {t3:.1f}s")

    # 估算 60 站点并行能力
    if ok >= 30:
        print(f"\n  ⚡ Parallel capacity: 60-site batch ~ {grand_total:.0f}s (p50={p50:.1f}s/article)")
        print(f"  ✅ pool_size=3 + SmartFetcher auto-route works for multi-site parallel scraping")
    else:
        print(f"\n  ⚠️ {len(all_results)-ok} failures — see details above")


if __name__ == "__main__":
    asyncio.run(main())
