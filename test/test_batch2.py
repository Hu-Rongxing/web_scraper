# -*- coding: utf-8 -*-
"""Batch 2 link test - new URLs"""

import asyncio
import sys
import time
import json
from path_setup import add_src_to_path
from datetime import datetime
from output_paths import output_path

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
add_src_to_path()

from web_scraper import SmartFetcher


TEST_URLS = [
    {"name": "tradingview_3", "url": "https://www.tradingview.com/news/reuters.com,2026:newsml_FWN42K0MV:0-dr-reddy-s-announces-first-to-market-launch-of-bosutinib-tablets-400mg-in-the-united-states/"},
    {"name": "yahoo_hk_1", "url": "https://hk.finance.yahoo.com/news/%E6%AE%BC%E7%89%8C-ceo-%E7%9F%B3%E6%B2%B9%E5%B8%82%E5%A0%B4%E9%9D%A2%E8%87%A8%E8%BF%9110%E5%84%84%E6%A1%B6%E4%BE%9B%E6%87%89%E7%BC%BA%E5%8F%A3-052754238.html"},
    {"name": "yahoo_hk_2", "url": "https://hk.finance.yahoo.com/news/%E4%BA%BA%E8%A1%8C-%E7%B9%BC%E7%BA%8C%E5%AF%A6%E6%96%BD%E9%81%A9%E5%BA%A6%E5%AF%AC%E9%AC%86%E8%B2%A8%E5%B9%A3%E6%94%BF%E7%AD%96-%E5%AF%86%E5%88%87%E9%97%9C%E6%B3%A8%E8%BC%B8%E5%85%A5%E6%80%A7%E9%80%9A%E8%84%B9%E5%BD%B1%E9%9F%BF-053058952.html"},
    {"name": "bloomberg_3", "url": "https://www.bloomberg.com/news/articles/2026-06-13/ber-zugang-wie-emirates-40-jahre-kampf-um-berlin-fluge-die-geduld-aller-testet"},
    {"name": "eeo_3", "url": "http://www.eeo.com.cn/2026/0613/913780.shtml"},
    {"name": "ft_4", "url": "https://www.ft.com/content/03c754d7-5188-481a-a920-ae5d35eebb3f"},
    {"name": "ft_5", "url": "https://www.ft.com/content/b31f1e09-5aae-4cad-af15-97adb15dba70"},
    {"name": "ft_6", "url": "https://www.ft.com/content/97b19a58-88e1-4b43-82a1-3e57013c8ebf"},
    {"name": "eeo_4", "url": "http://www.eeo.com.cn/2026/0613/913607.shtml"},
    {"name": "ft_7", "url": "https://www.ft.com/content/66f3005d-0342-4f30-a995-ad74b6bc6fac"},
    {"name": "jiemian_2", "url": "https://www.jiemian.com/article/14582532.html"},
    {"name": "wsj_cn", "url": "https://cn.wsj.com/articles/%E6%B3%95%E5%AE%98%E5%8F%AB%E5%81%9C%E7%89%B9%E6%9C%97%E6%99%AE-%E5%8F%8D%E6%AD%A6%E5%99%A8%E5%8C%96-%E5%9F%BA%E9%87%91-%E5%B9%B6%E8%A6%81%E6%B1%82%E7%A1%AE%E4%BF%9D%E8%AF%A5%E5%9F%BA%E9%87%91%E5%B7%B2%E5%BD%BB%E5%BA%95%E5%85%B3%E5%81%9C-a7a1b5b1?mod=cn_hp_lead_pos5"},
    {"name": "wsj_3", "url": "https://www.wsj.com/business/energy-oil/why-oil-prices-havent-shot-through-the-roofyet-bca1f60b?mod=rss_markets_main"},
    {"name": "tradingview_4", "url": "https://www.tradingview.com/news/DJN_DN20260612000711:0/"},
    {"name": "chinatimes", "url": "https://stock.10jqka.com.cn/20260613/c677439833.shtml"},
    {"name": "yahoo_finance_2", "url": "https://finance.yahoo.com/topic/economic-news/"},
    # DLQ retries
    {"name": "forbes_retry", "url": "https://www.forbes.com/sites/daraabasiita/2026/06/13/methanes-new-referee-is-a-machine/"},
    {"name": "bloomberg_retry", "url": "https://www.bloomberg.com/news/articles/2026-06-13/fed-boe-to-hold-rates-as-trump-seeks-iran-peace-deal"},
]


async def main():
    print(f"\n{'='*70}")
    print(f"Batch 2 Link Test - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Total URLs: {len(TEST_URLS)}")
    print(f"{'='*70}\n")

    results = []
    ok = 0
    fail = 0

    async with SmartFetcher() as fetcher:
        for i, tc in enumerate(TEST_URLS, 1):
            name = tc["name"]
            url = tc["url"]
            print(f"\n[{i}/{len(TEST_URLS)}] {name}")
            print(f"  URL: {url[:90]}...")

            try:
                t0 = time.monotonic()
                result = await fetcher.fetch(url)
                elapsed = time.monotonic() - t0

                status = "OK" if result.success else "FAIL"
                pipeline = result.meta.get("pipeline_level", 0) if hasattr(result, 'meta') else 0
                method = result.method or "-"

                r = {
                    "name": name,
                    "url": url,
                    "success": result.success,
                    "pipeline_level": pipeline,
                    "method": method,
                    "elapsed_ms": result.elapsed_ms,
                    "content_length": result.length,
                    "title": (result.title or "")[:120],
                    "error": (result.error or "")[:200],
                }
                results.append(r)

                if result.success:
                    ok += 1
                    print(f"  [{status}] P{pipeline} | {method} | {elapsed:.1f}s | {result.length} chars")
                    if result.title:
                        print(f"  Title: {result.title[:80]}")
                else:
                    fail += 1
                    print(f"  [{status}] {elapsed:.1f}s | {result.error[:120]}")

            except Exception as e:
                fail += 1
                print(f"  [EXCEPTION] {str(e)[:120]}")
                results.append({
                    "name": name, "url": url, "success": False,
                    "pipeline_level": 0, "method": "exception",
                    "elapsed_ms": 0, "content_length": 0,
                    "title": "", "error": str(e)[:200],
                })

            await asyncio.sleep(0.5)

    # Summary
    print(f"\n{'='*70}")
    print(f"SUMMARY: {ok}/{len(TEST_URLS)} success ({ok/len(TEST_URLS)*100:.0f}%)")
    print(f"{'='*70}")

    for r in results:
        s = "OK" if r["success"] else "FAIL"
        p = f"P{r['pipeline_level']}" if r["success"] else "-"
        print(f"  [{s}] {r['name']:20s} {p:4s} {r['elapsed_ms']:8.0f}ms {r['content_length']:6d} chars")

    # Save JSON
    out = output_path("test_results_batch2.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "total": len(TEST_URLS), "success": ok, "failed": fail,
            "results": results,
        }, f, indent=2, ensure_ascii=False)
    print(f"\nResults: {out}")


if __name__ == "__main__":
    asyncio.run(main())
