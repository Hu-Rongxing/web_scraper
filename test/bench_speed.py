# -*- coding: utf-8 -*-
"""Speed comparison: pool_size=3 vs pool_size=6

测试不同 pool_size 对并行抓取速度的影响.
"""

import sys, asyncio, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from article_reader import SmartFetcher
from asyncio import Semaphore

# 10 slow BPC news sites
BPC_URLS = [
    "https://www.wsj.com/market-data/quotes/index/US/DJIA",
    "https://www.wsj.com/market-data/quotes/index/US/SPX",
    "https://www.economist.com/leaders/2026/06/10/the-world-cup-paradox",
    "https://www.economist.com/leaders/2026/06/10/donald-trumps-least-bad-option-in-iran",
    "https://www.bloomberg.com/markets",
    "https://www.ft.com/",
    "https://www.nytimes.com/",
    "https://www.theguardian.com/international",
    "https://www.washingtonpost.com/",
    "https://www.bbc.com/news",
]

# 40 fast static sites
FAST_URLS = [
    "https://httpbin.org/get",
    "https://httpbin.org/html",
    "https://example.com/",
    "https://example.org/",
    "https://example.net/",
    "https://www.google.com/",
    "https://www.bing.com/",
    "https://www.wikipedia.org/",
    "https://github.com/",
    "https://stackoverflow.com/",
    "https://www.python.org/",
    "https://news.ycombinator.com/",
    "https://www.apple.com/",
    "https://www.microsoft.com/",
    "https://www.dropbox.com/",
    "https://www.notion.so/",
    "https://www.shopify.com/",
    "https://www.stripe.com/",
    "https://www.cloudflare.com/",
    "https://www.vercel.com/",
    "https://www.medium.com/",
    "https://www.quora.com/",
    "https://www.netflix.com/",
    "https://www.npmjs.com/package/react",
    "https://www.typescriptlang.org/",
    "https://developer.mozilla.org/en-US/",
    "https://www.baidu.com/",
    "https://www.zhihu.com/",
    "https://www.bilibili.com/",
    "https://www.sina.com.cn/",
    "https://pypi.org/",
    "https://www.nature.com/",
    "https://www.cnn.com/",
    "https://www.reuters.com/",
    "https://httpbin.org/links/10/0",
    "https://www.bbc.com/",
    "https://www.aljazeera.com/",
    "https://www.amazon.com/",
    "https://news.qq.com/rain/a/20260612A07LQF00",
    "https://news.qq.com/rain/a/20260612A03I7I00",
]


async def run_bench(label, pool_size, bpc_concurrency, fast_concurrency):
    """跑一轮基准测试."""
    print(f"\n{'='*70}")
    print(f"  {label}: pool_size={pool_size}, bpc_cc={bpc_concurrency}, fast_cc={fast_concurrency}")
    print(f"{'='*70}")

    f = SmartFetcher(pool_size=pool_size, preload=True, keep_alive=True)
    await f.start()

    sem_bpc = Semaphore(bpc_concurrency)
    sem_fast = Semaphore(fast_concurrency)
    results = []
    t0 = time.time()

    async def _fetch(i, url, sem, label):
        t1 = time.time()
        async with sem:
            try:
                r = await f.fetch(url)
                e = time.time() - t1
                results.append({"url": url, "ok": r.success, "elapsed": e, "chars": r.length})
                status = "OK" if r.success else "FAIL"
                print(f"  [{label} {i:2d}] {e:5.1f}s {status:4s}  {r.length:>6,} chars")
            except Exception as ex:
                e = time.time() - t1
                results.append({"url": url, "ok": False, "elapsed": e, "chars": 0})
                print(f"  [{label} {i:2d}] {e:5.1f}s ERROR  {str(ex)[:60]}")

    # BPC + Fast 混合并发
    tasks = []
    for i, url in enumerate(BPC_URLS, 1):
        tasks.append(_fetch(i, url, sem_bpc, "BPC"))
    for i, url in enumerate(FAST_URLS, 1):
        tasks.append(_fetch(i, url, sem_fast, "FAST"))

    await asyncio.gather(*tasks)
    total = time.time() - t0
    await f.shutdown()

    ok = sum(1 for r in results if r["ok"])
    times = [r["elapsed"] for r in results if r["ok"]]
    avg = sum(times) / len(times) if times else 0
    sorted_t = sorted(times) if times else []
    p50 = sorted_t[len(sorted_t)//2] if sorted_t else 0
    p90 = sorted_t[int(len(sorted_t)*0.9)] if sorted_t else 0

    print(f"\n  Result: {ok}/{len(results)} OK | avg={avg:.1f}s | p50={p50:.1f}s | p90={p90:.1f}s | total={total:.1f}s")
    return {"ok": ok, "total": total, "avg": avg, "p50": p50, "p90": p90}


async def main():
    print("=" * 70)
    print("  Speed Comparison: pool_size & concurrency impact")
    print("=" * 70)

    r1 = await run_bench("Baseline", pool_size=3, bpc_concurrency=3, fast_concurrency=10)
    r2 = await run_bench("Optimized", pool_size=6, bpc_concurrency=6, fast_concurrency=20)

    print(f"\n{'='*70}")
    print(f"  Comparison Summary")
    print(f"{'='*70}")
    print(f"")
    print(f"  {'Metric':20s} {'Baseline':>10s} {'Optimized':>10s} {'Improvement':>12s}")
    print(f"  {'-'*52}")
    print(f"  {'Success':20s} {r1['ok']:>10d} {r2['ok']:>10d}")
    print(f"  {'Total time':20s} {r1['total']:>9.1f}s {r2['total']:>9.1f}s {r1['total']/r2['total']:>11.1f}x")
    print(f"  {'Avg/article':20s} {r1['avg']:>9.1f}s {r2['avg']:>9.1f}s {r1['avg']/r2['avg']:>11.1f}x")
    speedup_total = r1["total"] / r2["total"] if r2["total"] > 0 else 0
    print(f"\n  ⚡ Speedup: {speedup_total:.1f}x faster with pool_size=6")


if __name__ == "__main__":
    asyncio.run(main())
