# -*- coding: utf-8 -*-
"""
Comprehensive test for all provided links.
Tests each URL through the full pipeline and records results.
"""

import asyncio
import json
import time
from datetime import datetime
from pathlib import Path
from output_paths import output_path

# Add project root to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

# Direct imports from project modules
from fetchers.smart import SmartFetcher


# Test URLs grouped by source
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
    
    # MarketWatch (via Jina Reader)
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


async def test_single_url(fetcher: SmartFetcher, test_case: dict) -> dict:
    """Test a single URL and return detailed result."""
    name = test_case["name"]
    url = test_case["url"]
    
    print(f"\n{'='*60}")
    print(f"Testing: {name}")
    print(f"URL: {url[:80]}...")
    print(f"{'='*60}")
    
    start_time = time.time()
    
    try:
        result = await fetcher.fetch(url)
        elapsed = time.time() - start_time
        
        test_result = {
            "name": name,
            "url": url,
            "success": result.success,
            "pipeline_level": result.meta.get("pipeline_level", 0),
            "method": result.method,
            "elapsed_ms": result.elapsed_ms,
            "content_length": result.length,
            "title": result.title[:100] if result.title else "",
            "error": result.error,
            "bypass_method": result.meta.get("bypass_method", ""),
            "wall_type": result.meta.get("wall_type", ""),
        }
        
        status = "✅ SUCCESS" if result.success else "❌ FAILED"
        print(f"\n{status}")
        print(f"  Pipeline: P{test_result['pipeline_level']}")
        print(f"  Method: {test_result['method']}")
        print(f"  Time: {elapsed:.1f}s ({result.elapsed_ms:.0f}ms)")
        print(f"  Content: {result.length} chars")
        if result.title:
            print(f"  Title: {result.title[:80]}...")
        if result.error:
            print(f"  Error: {result.error[:100]}...")
        if test_result.get("bypass_method"):
            print(f"  Bypass: {test_result['bypass_method']}")
            
        return test_result
        
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"\n❌ EXCEPTION: {str(e)[:100]}")
        return {
            "name": name,
            "url": url,
            "success": False,
            "pipeline_level": 0,
            "method": "exception",
            "elapsed_ms": elapsed * 1000,
            "content_length": 0,
            "title": "",
            "error": str(e)[:200],
            "bypass_method": "",
            "wall_type": "",
        }


async def main():
    """Run all tests."""
    print(f"\n{'#'*70}")
    print("# article_reader Link Test Suite")
    print(f"# Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"# Total URLs: {len(TEST_URLS)}")
    print(f"{'#'*70}\n")
    
    results = []
    
    async with SmartFetcher() as fetcher:
        # Test URLs sequentially to avoid overwhelming resources
        for i, test_case in enumerate(TEST_URLS, 1):
            print(f"\n[{i}/{len(TEST_URLS)}] ", end="")
            result = await test_single_url(fetcher, test_case)
            results.append(result)
            
            # Small delay between tests
            await asyncio.sleep(1)
    
    # Summary
    print(f"\n\n{'#'*70}")
    print("# TEST SUMMARY")
    print(f"{'#'*70}\n")
    
    success_count = sum(1 for r in results if r["success"])
    failed_count = len(results) - success_count
    
    print(f"Total: {len(results)}")
    print(f"Success: {success_count} ({success_count/len(results)*100:.1f}%)")
    print(f"Failed: {failed_count} ({failed_count/len(results)*100:.1f}%)")
    
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
    if failed_count > 0:
        print("\nFailed URLs:")
        for r in results:
            if not r["success"]:
                print(f"  - {r['name']}: {r['url'][:60]}...")
                print(f"    Error: {r['error'][:80]}...")
    
    # Save results to JSON
    output_file = output_path("test_results_all_links.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "total": len(results),
            "success": success_count,
            "failed": failed_count,
            "pipeline_distribution": pipeline_dist,
            "results": results,
        }, f, indent=2, ensure_ascii=False)
    
    print(f"\n\nResults saved to: {output_file}")
    
    # Generate markdown report
    report_file = output_path("test_results_all_links.md")
    with open(report_file, "w", encoding="utf-8") as f:
        f.write("# article_reader Link Test Report\n\n")
        f.write(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("## Summary\n\n")
        f.write(f"- **Total URLs:** {len(results)}\n")
        f.write(f"- **Success:** {success_count} ({success_count/len(results)*100:.1f}%)\n")
        f.write(f"- **Failed:** {failed_count} ({failed_count/len(results)*100:.1f}%)\n\n")
        
        f.write("## Pipeline Distribution\n\n")
        f.write("| Pipeline | Count |\n")
        f.write("|----------|-------|\n")
        for p in sorted(pipeline_dist.keys()):
            f.write(f"| P{p} | {pipeline_dist[p]} |\n")
        
        f.write("\n## Detailed Results\n\n")
        f.write("| # | Name | Status | Pipeline | Method | Time | Content | Error |\n")
        f.write("|---|------|--------|----------|--------|------|---------|-------|\n")
        
        for i, r in enumerate(results, 1):
            status = "✅" if r["success"] else "❌"
            pipeline = f"P{r['pipeline_level']}" if r["success"] else "-"
            method = r["method"][:20] if r["method"] else "-"
            time_str = f"{r['elapsed_ms']:.0f}ms"
            content = f"{r['content_length']} chars" if r["content_length"] > 0 else "-"
            error = r["error"][:30] if r["error"] else "-"
            
            f.write(f"| {i} | {r['name']} | {status} | {pipeline} | {method} | {time_str} | {content} | {error} |\n")
        
        f.write("\n## Failed URLs Analysis\n\n")
        for r in results:
            if not r["success"]:
                f.write(f"### {r['name']}\n")
                f.write(f"- **URL:** {r['url']}\n")
                f.write(f"- **Error:** {r['error']}\n")
                f.write(f"- **Method:** {r['method']}\n\n")
    
    print(f"Report saved to: {report_file}")


if __name__ == "__main__":
    asyncio.run(main())
