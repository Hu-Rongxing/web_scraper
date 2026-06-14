# -*- coding: utf-8 -*-
"""Speed test: preload mode + 3 sites average timing.

Phase 1: 用一个 SmartFetcher 提取各站链接
Phase 2: 用同一个 SmartFetcher 抓正文
全程单个 SmartFetcher 实例, 共享 BrowserPool.
"""

import sys
import asyncio
import time
from path_setup import add_src_to_path
add_src_to_path()

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from article_reader import SmartFetcher

SITES = [
    {"name": "WSJ", "list_url": "https://www.wsj.com"},
    {"name": "Economist", "list_url": "https://www.economist.com/weeklyedition/"},
    {"name": "Tencent", "list_url": "https://news.qq.com/"},
]


async def extract_links(f, site):
    """从列表页提取文章链接 (用 SmartFetcher 内部的 dynamic fetcher)."""
    name = site["name"]
    list_url = site["list_url"]
    print(f"\n  [{name}] 提取链接: {list_url}")

    slot = await f._shared_pool.acquire()
    page = await slot.context.new_page()
    articles = []

    try:
        await page.goto(list_url, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(10000)

        if name == "Economist":
            all_hrefs = await page.evaluate("""() => {
                return [...document.querySelectorAll('a[href]')].map(a => ({
                    href: a.href,
                    text: (a.textContent || '').trim()
                }));
            }""")
            seen = set()
            skip = ["/subscribe", "/login", "/auth", "/topics/", "/podcasts", "/newsletters",
                    "/video", "/audio/", "/weeklyedition/archive"]
            for h in all_hrefs:
                href = h["href"]
                text = h["text"]
                if not href or "economist.com" not in href:
                    continue
                if not text or len(text) < 15:
                    continue
                if any(s in href for s in skip):
                    continue
                u = href.split("?")[0].split("#")[0]
                parts = [p for p in u.split("/") if p]
                if len(parts) < 5 or u in seen:
                    continue
                seen.add(u)
                articles.append(u)
        elif name == "Tencent":
            links = await page.evaluate("""() => {
                const hrefs = [];
                document.querySelectorAll('a[href]').forEach(a => {
                    const h = a.href;
                    if (h && (h.includes('news.qq.com/rain/a/') || h.includes('new.qq.com/rain/a/') ||
                              h.includes('news.qq.com/omn/') || h.includes('new.qq.com/omn/'))) {
                        hrefs.push(h);
                    }
                });
                return [...new Set(hrefs)];
            }""")
            seen = set()
            for href in links:
                u = href.split("?")[0].split("#")[0]
                if u not in seen and len(u.split("/")) >= 5:
                    seen.add(u)
                    articles.append(u)
        else:  # WSJ
            all_hrefs = await page.evaluate("""() => [...document.querySelectorAll('a[href]')].map(a => a.href)""")
            seen = set()
            skip = ["/newsletters/", "/podcasts/", "/video/", "/live-coverage/",
                    "/photos/", "/graphics/", "login", "subscribe", "customercenter",
                    "/about", "/account"]
            for href in all_hrefs:
                if not href or "wsj.com" not in href:
                    continue
                u = href.split("?")[0].split("#")[0]
                if any(s in u for s in skip):
                    continue
                parts = [p for p in u.split("/") if p]
                if len(parts) >= 5 and u not in seen:
                    seen.add(u)
                    articles.append(u)

        print(f"  [{name}] found {len(articles)} candidates, top 5")
        return articles[:5]
    finally:
        await page.close()
        await f._shared_pool.release(slot)


async def main():
    # ---- 单一 SmartFetcher, 共享池 size=1 (避免多实例冲突) ----
    f = SmartFetcher(pool_size=1, preload=True, keep_alive=True)
    await f.start()

    # ---- Phase 1: 提取链接 ----
    print("=" * 70)
    print("Phase 1: Extract article links from all 3 sites")
    print("=" * 70)
    links_map = {}
    for site in SITES:
        links = await extract_links(f, site)
        links_map[site["name"]] = links

    # ---- Phase 2: 抓取正文并计时 ----
    print("\n" + "=" * 70)
    print("Phase 2: Fetch articles (preload=True, pool_size=1)")
    print("=" * 70)

    print("\nTiming run: 5 articles each from 3 sites, 15 total\n")
    total_start = time.time()
    all_times = []
    site_results = {}

    for name, urls in links_map.items():
        site_start = time.time()
        results = []
        for i, url in enumerate(urls, 1):
            t0 = time.time()
            try:
                r = await f.fetch(url)
                elapsed = time.time() - t0
                results.append((r, elapsed))
                status = "OK" if r.success else "FAIL"
                title = (r.title or "")[:55]
                print(f"  [{name} #{i}] {elapsed:5.1f}s {status} {r.length:>6,} chars  {title}")
            except Exception as e:
                elapsed = time.time() - t0
                print(f"  [{name} #{i}] {elapsed:5.1f}s ERROR: {e}")
                results.append((None, elapsed))
        site_elapsed = time.time() - site_start
        site_results[name] = (results, site_elapsed)
        all_times.extend([t for _, t in results])

    total_elapsed = time.time() - total_start

    # ---- Cleanup ----
    await f.shutdown()

    # ---- Report ----
    print("\n" + "=" * 70)
    print("Results Summary")
    print("=" * 70)

    for name, (results, site_total) in site_results.items():
        times = [t for _, t in results]
        successes = [r for r, _ in results if r and r.success]
        chars = sum(r.length for r in successes)
        avg = sum(times) / len(times) if times else 0
        print(f"\n  {name}:")
        print(f"    Success: {len(successes)}/{len(results)}")
        print(f"    Avg time: {avg:.1f}s")
        if times:
            print(f"    Range:   {min(times):.1f}s ~ {max(times):.1f}s")
        print(f"    Total chars: {chars:,}")
        print(f"    Site total: {site_total:.1f}s")

    total_success = sum(len([r for r,_ in site_results[n][0] if r and r.success]) for n in site_results)
    print("\n  Overall:")
    print(f"    Total time: {total_elapsed:.1f}s")
    print(f"    Articles: {total_success}/{len(all_times)} success")
    avg = sum(all_times) / len(all_times) if all_times else 0
    print(f"    Avg/article: {avg:.1f}s")
    if all_times:
        sorted_t = sorted(all_times)
        p50 = sorted_t[len(sorted_t)//2]
        p90 = sorted_t[int(len(sorted_t)*0.9)]
        print(f"    Range: {min(all_times):.1f}s ~ {max(all_times):.1f}s")
        print(f"    p50: {p50:.1f}s  p90: {p90:.1f}s")

    print("\n  # preload=True eliminated cold-start browser launch cost.")


if __name__ == "__main__":
    asyncio.run(main())
