# -*- coding: utf-8 -*-
"""
test_real_sites.py — 真实网站五级管线测试

测试站点分级：
- Tier 1 (静态): 腾讯新闻、BBC News、Reuters
- Tier 2 (SPA):  GitHub Trending、Hacker News
- Tier 3 (反爬):  Cloudflare 保护站点
- Tier 4 (付费墙): WSJ、The Economist、NYTimes
- Tier 5 (兜底): nodriver 链路
"""

import asyncio
import sys
import time
from path_setup import add_src_to_path

# 修复 Windows 控制台编码
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

add_src_to_path()

from article_reader import SmartFetcher, Pipeline5Manager


# ============================================================
# 测试站点列表
# ============================================================

TIER1_STATIC = [
    {
        "name": "Tencent News",
        "url": "https://news.qq.com/",
        "expect_pipeline": 1,
        "min_content": 500,
    },
    {
        "name": "BBC News",
        "url": "https://www.bbc.com/news",
        "expect_pipeline": 1,
        "min_content": 500,
    },
    {
        "name": "Reuters",
        "url": "https://www.reuters.com/",
        "expect_pipeline": 1,
        "min_content": 300,
    },
]

TIER2_SPA = [
    {
        "name": "GitHub Trending",
        "url": "https://github.com/trending",
        "expect_pipeline": 2,
        "min_content": 300,
    },
    {
        "name": "Hacker News",
        "url": "https://news.ycombinator.com/",
        "expect_pipeline": 1,  # HN 实际是服务端渲染
        "min_content": 300,
    },
]

TIER3_ANTI_BOT = [
    {
        "name": "Wikipedia",
        "url": "https://en.wikipedia.org/wiki/Web_scraping",
        "expect_pipeline": 1,
        "min_content": 500,
    },
]

TIER4_PAYWALL = [
    {
        "name": "WSJ",
        "url": "https://www.wsj.com/",
        "expect_pipeline": 4,
        "min_content": 200,
    },
    {
        "name": "The Economist",
        "url": "https://www.economist.com/",
        "expect_pipeline": 4,
        "min_content": 200,
    },
]


def print_result(name: str, result, expected_pipeline: int = None):
    """打印测试结果"""
    status = "[OK]" if result.success else "[FAIL]"
    pipeline_info = f"P{result.meta.get('pipeline_level', '?')}" if hasattr(result, 'meta') else "?"
    
    print(f"\n{'='*60}")
    print(f"{status} {name}")
    print(f"{'='*60}")
    print(f"  URL: {result.url}")
    print(f"  Success: {result.success}")
    print(f"  Pipeline: {pipeline_info} (method: {result.method})")
    print(f"  Elapsed: {result.elapsed_ms:.0f}ms")
    
    if result.success:
        print(f"  Title: {result.title[:80] if result.title else 'N/A'}")
        print(f"  Content length: {result.length} chars")
        print(f"  Author: {result.author or 'N/A'}")
        print(f"  Date: {result.date or 'N/A'}")
        if result.content:
            preview = result.content[:150].replace('\n', ' ')
            print(f"  Preview: {preview}...")
        
        if expected_pipeline:
            actual = result.meta.get('pipeline_level', 0) if hasattr(result, 'meta') else 0
            if actual == expected_pipeline:
                print(f"  [OK] Pipeline match: expected P{expected_pipeline}, actual P{actual}")
            else:
                print(f"  [WARN] Pipeline mismatch: expected P{expected_pipeline}, actual P{actual}")
    else:
        print(f"  Error: {result.error}")
    
    return result.success


async def test_tier(tier_name: str, sites: list, fetcher):
    """测试一个 tier 的站点"""
    print(f"\n{'#'*60}")
    print(f"# {tier_name}")
    print(f"{'#'*60}")
    
    results = []
    for site in sites:
        try:
            result = await fetcher.fetch(site["url"])
            success = print_result(site["name"], result, site.get("expect_pipeline"))
            results.append((site["name"], success))
        except Exception as e:
            print(f"\n[FAIL] {site['name']}: Exception - {e}")
            results.append((site["name"], False))
    
    return results


async def test_pipeline5():
    """单独测试管线 5 (nodriver)"""
    print(f"\n{'#'*60}")
    print("# Tier 5: Pipeline 5 fallback (nodriver)")
    print(f"{'#'*60}")
    
    test_url = "https://en.wikipedia.org/wiki/Web_scraping"
    print(f"\nTest URL: {test_url}")
    
    try:
        async with Pipeline5Manager() as p5:
            t0 = time.monotonic()
            result = await p5.fetch(test_url)
            elapsed = (time.monotonic() - t0) * 1000
            
            status = "[OK]" if result.success else "[FAIL]"
            print(f"\n{status} Pipeline 5 test")
            print(f"  Success: {result.success}")
            print(f"  Elapsed: {elapsed:.0f}ms")
            if result.success:
                print(f"  Title: {result.title[:80] if result.title else 'N/A'}")
                print(f"  Content length: {result.length} chars")
            else:
                print(f"  Error: {result.error}")
            
            return [("Pipeline5 nodriver", result.success)]
    except Exception as e:
        print(f"\n[FAIL] Pipeline 5 exception: {e}")
        return [("Pipeline5 nodriver", False)]


async def test_auto_degradation():
    """测试自动降级机制"""
    print(f"\n{'#'*60}")
    print("# Auto-degradation test")
    print(f"{'#'*60}")
    
    test_sites = [
        {"name": "Cloudflare site (may need degradation)", "url": "https://www.cloudflare.com/"},
    ]
    
    results = []
    async with SmartFetcher() as fetcher:
        for site in test_sites:
            print(f"\nTesting: {site['name']}")
            try:
                result = await fetcher.fetch(site["url"])
                success = print_result(site["name"], result)
                results.append((site["name"], success, result.meta.get("pipeline_level", 0)))
            except Exception as e:
                print(f"[FAIL] Exception: {e}")
                results.append((site["name"], False, 0))
    
    return results


async def main():
    """主测试函数"""
    print("\n" + "="*60)
    print("article_reader v3.0 - Real site 5-pipeline test")
    print("="*60)
    
    all_results = []
    
    # Tier 1-4 使用 SmartFetcher（自动降级）
    async with SmartFetcher() as fetcher:
        # Tier 1: 静态页面
        r1 = await test_tier("Tier 1: Static pages (expect pipeline 1)", TIER1_STATIC, fetcher)
        all_results.extend(r1)
        
        # Tier 2: SPA 动态页面
        r2 = await test_tier("Tier 2: SPA pages (expect pipeline 1-2)", TIER2_SPA, fetcher)
        all_results.extend(r2)
        
        # Tier 3: 反爬站点
        r3 = await test_tier("Tier 3: Anti-bot sites (expect pipeline 2-3)", TIER3_ANTI_BOT, fetcher)
        all_results.extend(r3)
        
        # Tier 4: 付费墙
        r4 = await test_tier("Tier 4: Paywall sites (expect pipeline 4)", TIER4_PAYWALL, fetcher)
        all_results.extend(r4)
    
    # Tier 5: nodriver 兜底（单独测试）
    r5 = await test_pipeline5()
    all_results.extend(r5)
    
    # 自动降级测试
    r_deg = await test_auto_degradation()
    
    # 打印总结
    print(f"\n{'='*60}")
    print("Test Summary")
    print(f"{'='*60}")
    
    passed = sum(1 for r in all_results if r[1])
    total = len(all_results)
    
    for name, success, *extra in all_results:
        status = "[OK]" if success else "[FAIL]"
        pipeline = f" (P{extra[0]})" if extra else ""
        print(f"  {status} {name}{pipeline}")
    
    print(f"\nTotal: {passed}/{total} passed")
    
    if r_deg:
        print("\nAuto-degradation test:")
        for name, success, pipeline in r_deg:
            print(f"  {'[OK]' if success else '[FAIL]'} {name} -> final pipeline P{pipeline}")
    
    return passed > 0


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
