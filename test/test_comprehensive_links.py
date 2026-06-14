# -*- coding: utf-8 -*-
"""
Comprehensive link testing for article_reader project.
Tests all provided URLs and records success/failure with methods.
"""

import asyncio
import sys
import time
import json
from pathlib import Path
from datetime import datetime
from output_paths import output_path

# Fix Windows console encoding
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
# article_reader package is in D:\oc_workspace\main\article_reader
# So we need to add D:\oc_workspace\main to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from article_reader import SmartFetcher


# All test URLs organized by source
TEST_URLS = [
    # Yahoo Finance
    {"name": "yahoo_finance", "url": "https://finance.yahoo.com/topic/economic-news/"},
    
    # Forbes
    {"name": "forbes", "url": "https://www.forbes.com/sites/daraabasiita/2026/06/13/methanes-new-referee-is-a-machine/"},
    
    # Bloomberg (paywall)
    {"name": "bloomberg_1", "url": "https://www.bloomberg.com/news/articles/2026-06-13/fed-boe-to-hold-rates-as-trump-seeks-iran-peace-deal"},
    {"name": "bloomberg_2", "url": "https://www.bloomberg.com/news/articles/2026-06-13/clo-etfs-boom-on-higher-rates-private-debt-woes-credit-weekly"},
    
    # Sina Finance
    {"name": "sina_finance", "url": "https://finance.sina.com.cn/wm/2026-06-14/doc-inicipwa7707977.shtml"},
    
    # WSJ (paywall)
    {"name": "wsj_1", "url": "https://www.wsj.com/finance/currencies/asia-currency-ai-energy-8d4f4cb4?mod=rss_markets_main"},
    {"name": "wsj_2", "url": "https://www.wsj.com/finance/investing/america-has-a-credit-card-problem-just-not-the-one-you-think-da0859be?mod=rss_markets_main"},
    
    # QQ Finance
    {"name": "qq_finance_1", "url": "https://news.qq.com/rain/a/20260614A0243500"},
    {"name": "qq_finance_2", "url": "https://news.qq.com/rain/a/20260613A07XER00"},
    
    # MarketWatch (via Jina Reader - these are proxied)
    {"name": "marketwatch_1", "url": "https://r.jina.ai/http://https://www.marketwatch.com/story/gold-has-tumbled-during-the-iran-war-exposing-a-massive-myth-about-geopolitical-risk-15bd2c94?mod=mw_rss_topstories"},
    {"name": "marketwatch_2", "url": "https://r.jina.ai/http://https://www.marketwatch.com/story/the-world-cup-could-deliver-fox-a-ratings-bonanza-there-will-be-all-sorts-of-viewership-records-950604d3?mod=mw_rss_topstories"},
    {"name": "marketwatch_3", "url": "https://r.jina.ai/http://https://www.marketwatch.com/story/rip-euro-summer-americans-are-trading-tuscany-for-tacoma-thanks-to-soaring-airfares-44751904?mod=mw_rss_topstories"},
    {"name": "marketwatch_4", "url": "https://r.jina.ai/http://https://www.marketwatch.com/story/spacex-employees-now-have-enough-wealth-on-paper-to-buy-every-home-in-this-texas-city-ce0842be?mod=mw_rss_topstories"},
    {"name": "marketwatch_5", "url": "https://r.jina.ai/http://https://www.marketwatch.com/story/the-rich-keep-spending-money-on-unapologetic-luxury-and-its-raising-prices-on-everyday-goods-for-everyone-cdc4546b?mod=mw_rss_topstories"},
    {"name": "marketwatch_6", "url": "https://r.jina.ai/http://https://www.marketwatch.com/story/defaults-in-debt-markets-are-starting-again-warns-pimco-heres-the-bond-giants-game-plan-16559c6d?mod=mw_rss_topstories"},
    
    # TradingView
    {"name": "tradingview_1", "url": "https://www.tradingview.com/news/reuters.com,2026:newsml_TUA6208Y9:0-genmab-announces-epcoritamab-monotherapy-and-epcoritamab-based-combination-regimens-demonstrate-high-response-rates-in-elderly-patients-with-newly-diagnosed-diffuse-large-b-cell-lymphoma/"},
    {"name": "tradingview_2", "url": "https://www.tradingview.com/news/reuters.com,2026:newsml_FWN42K0GD:0-investment-firms-join-donald-trump-s-100bn-race-for-venezuelan-oil-ft/"},
    
    # CNBC
    {"name": "cnbc", "url": "https://www.cnbc.com/2026/06/13/from-10percent-chance-of-success-to-2-trillion-spacexs-historic-ipo.html"},
    
    # STCN (Securities Times)
    {"name": "stcn_1", "url": "https://www.stcn.com/article/detail/3960188.html"},
    {"name": "stcn_2", "url": "https://www.stcn.com/article/detail/3960155.html"},
    
    # Wallstreetcn Live (API)
    {"name": "wallstreetcn_1", "url": "https://api-one-wscn.awtmt.com/apiv1/content/lives/3119152"},
    {"name": "wallstreetcn_2", "url": "https://api-one-wscn.awtmt.com/apiv1/content/lives/3119143"},
    
    # EEO (Economic Observer)
    {"name": "eeo_1", "url": "http://www.eeo.com.cn/2026/0613/914470.shtml"},
    {"name": "eeo_2", "url": "http://www.eeo.com.cn/2026/0613/914267.shtml"},
    
    # 21Jingji (21st Century Business Herald)
    {"name": "yicai_21", "url": "https://www.21jingji.com/article/20260613/herald/01b8fe7492e204f033505e388e327378.html"},
    
    # FT (Financial Times - paywall)
    {"name": "ft_1", "url": "https://www.ft.com/content/a7f4246d-9ae2-4f7b-90af-e5a53c52203b"},
    {"name": "ft_2", "url": "https://www.ft.com/content/3aef5865-962c-4010-8915-6b573b2ad705"},
    {"name": "ft_3", "url": "https://www.ft.com/content/20509c5d-e995-4670-83f5-d3d705671ee1?syn-25a6b1a6=1"},
    
    # CS (China Securities Journal)
    {"name": "cs", "url": "https://jnzstatic.cs.com.cn/zzb/htmlInfo/03bc5854363a4c609195f01c661365c0.html"},
    
    # BJNews (Beijing News)
    {"name": "bjnews", "url": "https://www.bjnews.com.cn/detail/1781343192129082.html"},
    
    # Jiemian
    {"name": "jiemian", "url": "https://www.jiemian.com/article/14583449.html"},
    
    # CLS (Cailian Press)
    {"name": "cls", "url": "https://www.cls.cn/detail/2399081"},
]


def print_result(name: str, result, elapsed_time: float):
    """Print test result for a single URL."""
    status = "[OK]" if result.success else "[FAIL]"
    pipeline_info = f"P{result.meta.get('pipeline_level', '?')}" if hasattr(result, 'meta') else "?"
    
    print(f"\n{'='*70}")
    print(f"{status} {name}")
    print(f"{'='*70}")
    print(f"  URL: {result.url[:80]}...")
    print(f"  Success: {result.success}")
    print(f"  Pipeline: {pipeline_info} (method: {result.method})")
    print(f"  Elapsed: {elapsed_time:.1f}s ({result.elapsed_ms:.0f}ms)")
    
    if result.success:
        print(f"  Title: {result.title[:100] if result.title else 'N/A'}")
        print(f"  Content length: {result.length} chars")
        print(f"  Author: {result.author or 'N/A'}")
        print(f"  Date: {result.date or 'N/A'}")
        if result.content:
            preview = result.content[:200].replace('\n', ' ')
            print(f"  Preview: {preview}...")
    else:
        print(f"  Error: {result.error}")
    
    return result.success


async def main():
    """Main test function."""
    print("\n" + "="*70)
    print("article_reader v3.1 - Comprehensive Link Test")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Total URLs to test: {len(TEST_URLS)}")
    print("="*70)
    
    results = []
    success_count = 0
    fail_count = 0
    
    async with SmartFetcher() as fetcher:
        for i, test_case in enumerate(TEST_URLS, 1):
            name = test_case["name"]
            url = test_case["url"]
            
            print(f"\n[{i}/{len(TEST_URLS)}] Testing: {name}")
            print(f"URL: {url[:80]}...")
            
            try:
                t0 = time.monotonic()
                result = await fetcher.fetch(url)
                elapsed = time.monotonic() - t0
                
                success = print_result(name, result, elapsed)
                
                results.append({
                    "name": name,
                    "url": url,
                    "success": result.success,
                    "pipeline_level": result.meta.get("pipeline_level", 0) if hasattr(result, 'meta') else 0,
                    "method": result.method,
                    "elapsed_ms": result.elapsed_ms,
                    "content_length": result.length,
                    "title": result.title[:100] if result.title else "",
                    "error": result.error or "",
                })
                
                if success:
                    success_count += 1
                else:
                    fail_count += 1
                    
            except Exception as e:
                print(f"[FAIL] {name}: Exception - {e}")
                fail_count += 1
                results.append({
                    "name": name,
                    "url": url,
                    "success": False,
                    "pipeline_level": 0,
                    "method": "exception",
                    "elapsed_ms": 0,
                    "content_length": 0,
                    "title": "",
                    "error": str(e),
                })
            
            # Small delay between tests to avoid overwhelming resources
            await asyncio.sleep(0.5)
    
    # Print summary
    print(f"\n{'='*70}")
    print("TEST SUMMARY")
    print(f"{'='*70}")
    print(f"Total: {len(TEST_URLS)}")
    print(f"Success: {success_count} ({success_count/len(TEST_URLS)*100:.1f}%)")
    print(f"Failed: {fail_count} ({fail_count/len(TEST_URLS)*100:.1f}%)")
    
    # Pipeline distribution
    pipeline_dist = {}
    for r in results:
        if r["success"]:
            p = r["pipeline_level"]
            pipeline_dist[p] = pipeline_dist.get(p, 0) + 1
    
    print("\nPipeline Distribution:")
    for p in sorted(pipeline_dist.keys()):
        print(f"  P{p}: {pipeline_dist[p]}")
    
    # Failed URLs
    if fail_count > 0:
        print("\nFailed URLs:")
        for r in results:
            if not r["success"]:
                print(f"  - {r['name']}: {r['url'][:60]}...")
                print(f"    Error: {r['error'][:100]}...")
    
    # Save results to JSON
    output_file = output_path("test_results_comprehensive.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "total": len(TEST_URLS),
            "success": success_count,
            "failed": fail_count,
            "pipeline_distribution": pipeline_dist,
            "results": results,
        }, f, indent=2, ensure_ascii=False)
    
    print(f"\n\nResults saved to: {output_file}")
    
    # Generate markdown report
    report_file = output_path("test_results_comprehensive.md")
    with open(report_file, "w", encoding="utf-8") as f:
        f.write("# article_reader Comprehensive Link Test Report\n\n")
        f.write(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("## Summary\n\n")
        f.write(f"- **Total URLs:** {len(TEST_URLS)}\n")
        f.write(f"- **Success:** {success_count} ({success_count/len(TEST_URLS)*100:.1f}%)\n")
        f.write(f"- **Failed:** {fail_count} ({fail_count/len(TEST_URLS)*100:.1f}%)\n\n")
        
        f.write("## Pipeline Distribution\n\n")
        f.write("| Pipeline | Count |\n")
        f.write("|----------|-------|\n")
        for p in sorted(pipeline_dist.keys()):
            f.write(f"| P{p} | {pipeline_dist[p]} |\n")
        
        f.write("\n## Detailed Results\n\n")
        f.write("| # | Name | Status | Pipeline | Method | Time | Content |\n")
        f.write("|---|------|--------|----------|--------|------|--------|\n")
        
        for i, r in enumerate(results, 1):
            status = "✅" if r["success"] else "❌"
            pipeline = f"P{r['pipeline_level']}" if r["success"] else "-"
            method = r["method"][:25] if r["method"] else "-"
            time_str = f"{r['elapsed_ms']:.0f}ms"
            content = f"{r['content_length']} chars" if r["content_length"] > 0 else "-"
            
            f.write(f"| {i} | {r['name']} | {status} | {pipeline} | {method} | {time_str} | {content} |\n")
        
        f.write("\n## Failed URLs Analysis\n\n")
        for r in results:
            if not r["success"]:
                f.write(f"### {r['name']}\n")
                f.write(f"- **URL:** {r['url']}\n")
                f.write(f"- **Error:** {r['error']}\n")
                f.write(f"- **Method:** {r['method']}\n\n")
    
    print(f"Report saved to: {report_file}")
    
    return success_count > 0


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
