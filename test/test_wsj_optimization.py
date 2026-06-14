# -*- coding: utf-8 -*-
"""
WSJ / cn.WSJ 涓撻」浼樺寲娴嬭瘯
娴嬭瘯缁村害锛?1. P4 wait 鏃堕棿: 5s(default) / 8s / 12s
2. 鎻愬彇绛栫暐: trafilatura vs Scrapling fallback
3. wait_until: domcontentloaded vs networkidle
4. URL 鍙傛暟: RSS feed / direct
"""

import asyncio
import sys
import time
import json
from path_setup import add_src_to_path
from datetime import datetime
from dataclasses import dataclass
from typing import Optional
from output_paths import output_path

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
add_src_to_path()

from article_reader import SmartFetcher
from article_reader.config import PAGE_GOTO_TIMEOUT


# ============================================================
# Test URLs
# ============================================================
WSJ_TEST_URLS = [
    # cn.WSJ - SKIPPED: P4 also returns 403 (cn.wsj has stronger anti-bot than .com)
    
    # wsj.com with RSS mod (more content-friendly)
    {"name": "wsj_currencies_rss", "url": "https://www.wsj.com/finance/currencies/asia-currency-ai-energy-8d4f4cb4?mod=rss_markets_main"},
    {"name": "wsj_energy_oil_rss", "url": "https://www.wsj.com/business/energy-oil/why-oil-prices-havent-shot-through-the-roofyet-bca1f60b?mod=rss_markets_main"},
    {"name": "wsj_credit_card_rss", "url": "https://www.wsj.com/finance/investing/america-has-a-credit-card-problem-just-not-the-one-you-think-da0859be?mod=rss_markets_main"},
    
    # wsj.com without RSS mod (direct)
    {"name": "wsj_currencies_dir", "url": "https://www.wsj.com/finance/currencies/asia-currency-ai-energy-8d4f4cb4"},
    {"name": "wsj_energy_oil_dir", "url": "https://www.wsj.com/business/energy-oil/why-oil-prices-havent-shot-through-the-roofyet-bca1f60b"},
    {"name": "wsj_credit_card_dir", "url": "https://www.wsj.com/finance/investing/america-has-a-credit-card-problem-just-not-the-one-you-think-da0859be"},
]


@dataclass
class TestConfig:
    """Single test configuration."""
    name: str
    wait_ms: int
    wait_until: str  # "domcontentloaded" | "networkidle" | "load"
    extractor: str   # "trafilatura" | "scrapling"


@dataclass
class TestResult:
    config: TestConfig
    url: str
    success: bool
    content_length: int
    title: str = ""
    elapsed_ms: float = 0
    start_time: float = 0
    end_time: float = 0
    error: str = ""
    preview: str = ""


async def run_single_test(
    url: str,
    config: TestConfig,
    fetcher: SmartFetcher,
) -> TestResult:
    """Run a single test with specific config."""
    
    t0 = time.monotonic()
    
    try:
        # We need to bypass the normal pipeline and directly control P4 params.
        # Run a custom P4-like approach with modified parameters.
        from article_reader.browser_pool import BrowserSlot
        from article_reader.content_extractor import ContentExtractor
        from article_reader.config import MIN_CONTENT_LENGTH, PIPELINE_FAILURE_SIGNALS
        
        pool_c = fetcher._pipeline._pool_c
        if pool_c is None:
            return TestResult(
                config=config, url=url, success=False,
                error="Pool C not available", elapsed_ms=(time.monotonic() - t0) * 1000,
            )
        
        slot: Optional[BrowserSlot] = None
        page = None
        
        try:
            slot = await pool_c.acquire()
            page = await slot.context.new_page()
            page.set_default_timeout(PAGE_GOTO_TIMEOUT)
            
            # Modified render with configurable parameters
            await page.goto(url, wait_until=config.wait_until, timeout=PAGE_GOTO_TIMEOUT)
            
            try:
                await page.wait_for_selector(
                    "article, main, .content",
                    timeout=config.wait_ms,
                )
            except Exception:
                pass
            
            # Scroll lazy-load
            prev_height = 0
            max_scrolls = 15
            for _ in range(max_scrolls):
                current_height = await page.evaluate("document.body.scrollHeight")
                if current_height == prev_height:
                    break
                prev_height = current_height
                await page.evaluate("window.scrollBy(0, window.innerHeight)")
                await asyncio.sleep(1.0)
            
            html = await page.content()
            title = await page.title()
            
            # Check for pipeline failure
            html_lower = html.lower()
            for signal in PIPELINE_FAILURE_SIGNALS:
                if signal in html_lower:
                    t1 = time.monotonic()
                    return TestResult(
                        config=config, url=url, success=False,
                        content_length=0, title=title,
                        elapsed_ms=(t1 - t0) * 1000,
                        error=f"Block signal: {signal}",
                    )
            
            # Extract with configured extractor
            if config.extractor == "scrapling":
                extracted = ContentExtractor(strategy="trafilatura")._extract_scrapling(
                    html,
                    method="scrapling_diagnostic",
                )
                content = extracted.content
                extracted_title = extracted.title or title
            else:
                extracted = ContentExtractor(strategy="trafilatura").extract(html, url)
                content = extracted.content
                extracted_title = extracted.title or title
            
            t1 = time.monotonic()
            success = len(content) >= MIN_CONTENT_LENGTH
            
            return TestResult(
                config=config, url=url, success=success,
                content_length=len(content),
                title=extracted_title[:100] if extracted_title else title[:100],
                elapsed_ms=(t1 - t0) * 1000,
                error="" if success else f"Content too short: {len(content)} chars",
                preview=content[:150] if content else "",
            )
            
        finally:
            if page:
                try:
                    await page.close()
                except Exception:
                    pass
            if slot:
                await pool_c.release_and_destroy(slot)
                
    except Exception as e:
        t1 = time.monotonic()
        return TestResult(
            config=config, url=url, success=False,
            content_length=0,
            elapsed_ms=(t1 - t0) * 1000,
            error=str(e)[:200],
        )


# ============================================================
# Test configurations to try - reduced set to speed up
TEST_CONFIGS = [
    # Baseline: default (5s wait, domcontentloaded, trafilatura)
    TestConfig("baseline_default", wait_ms=5000, wait_until="domcontentloaded", extractor="trafilatura"),
    
    # Longer wait with domcontentloaded
    TestConfig("wait_10s", wait_ms=10000, wait_until="domcontentloaded", extractor="trafilatura"),
    
    # Scrapling fallback extractor (5s + 10s)
    TestConfig("scrapling_5s", wait_ms=5000, wait_until="domcontentloaded", extractor="scrapling"),
    TestConfig("scrapling_10s", wait_ms=10000, wait_until="domcontentloaded", extractor="scrapling"),
    
    # Best combo: Scrapling fallback + longer + load (waits for all resources)
    TestConfig("scrapling_10s_load", wait_ms=10000, wait_until="load", extractor="scrapling"),
]


async def main():
    print(f"\n{'='*80}")
    print("WSJ / cn.WSJ Optimization Test Suite")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"URLs: {len(WSJ_TEST_URLS)} | Configs: {len(TEST_CONFIGS)}")
    print(f"Total tests: {len(WSJ_TEST_URLS) * len(TEST_CONFIGS)}")
    print(f"{'='*80}\n")
    
    all_results = []
    
    async with SmartFetcher() as fetcher:
        for url_idx, url_info in enumerate(WSJ_TEST_URLS, 1):
            print(f"\n{'#'*80}")
            print(f"# [{url_idx}/{len(WSJ_TEST_URLS)}] {url_info['name']}")
            print(f"# URL: {url_info['url'][:90]}...")
            print(f"{'#'*80}")
            
            url_results = []
            
            for cfg_idx, cfg in enumerate(TEST_CONFIGS, 1):
                print(f"\n  [{cfg_idx}/{len(TEST_CONFIGS)}] {cfg.name}: "
                      f"wait={cfg.wait_ms}ms until={cfg.wait_until} extract={cfg.extractor} ...", end="")
                
                result = await run_single_test(url_info["url"], cfg, fetcher)
                url_results.append(result)
                
                if result.success:
                    print(f" [OK] {result.content_length} chars | {result.elapsed_ms:.0f}ms")
                    print(f"       Title: {result.title[:70]}...")
                else:
                    print(f" [FAIL] {result.error[:80]} | {result.elapsed_ms:.0f}ms")
                
                all_results.append(result)
                
                # Short pause between tests
                await asyncio.sleep(2)
    
    # ============================================================
    # Analysis & Summary
    # ============================================================
    print(f"\n\n{'='*80}")
    print("OPTIMIZATION ANALYSIS")
    print(f"{'='*80}\n")
    
    # Group by URL
    url_groups = {}
    for r in all_results:
        key = next((u["name"] for u in WSJ_TEST_URLS if u["url"] == r.url), r.url)
        if key not in url_groups:
            url_groups[key] = []
        url_groups[key].append(r)
    
    for url_name, results in url_groups.items():
        print(f"\n--- {url_name} ---")
        print(f"{'Config':<25s} {'Status':>6s} {'Chars':>8s} {'Time':>8s} {'Error'}")
        print(f"{'-'*25} {'-'*6} {'-'*8} {'-'*8} {'-'*20}")
        
        best_content = 0
        best_config = ""
        
        for r in results:
            status = "OK" if r.success else "FAIL"
            chars = f"{r.content_length}" if r.content_length > 0 else "-"
            t = f"{r.elapsed_ms:.0f}ms"
            err = r.error[:25] if r.error else "-"
            print(f"{r.config.name:<25s} {status:>6s} {chars:>8s} {t:>8s} {err}")
            
            if r.content_length > best_content:
                best_content = r.content_length
                best_config = r.config.name
        
        if best_content > 0:
            print(f"  >> Best: {best_config} ({best_content} chars)")
    
    # Cross-analysis
    print(f"\n\n{'='*80}")
    print("CROSS-ANALYSIS (by config, avg across all URLs)")
    print(f"{'='*80}")
    
    config_stats = {}
    for r in all_results:
        name = r.config.name
        if name not in config_stats:
            config_stats[name] = {"total": 0, "success": 0, "avg_chars": 0, "avg_time": 0}
        stats = config_stats[name]
        stats["total"] += 1
        if r.success:
            stats["success"] += 1
        stats["avg_chars"] += r.content_length
        stats["avg_time"] += r.elapsed_ms
    
    print(f"{'Config':<25s} {'Success':>8s} {'AvgChars':>10s} {'AvgTime':>10s}")
    print(f"{'-'*25} {'-'*8} {'-'*10} {'-'*10}")
    for name in sorted(config_stats.keys()):
        s = config_stats[name]
        rate = f"{s['success']}/{s['total']}"
        avg_c = f"{s['avg_chars']/s['total']:.0f}"
        avg_t = f"{s['avg_time']/s['total']:.0f}ms"
        print(f"{name:<25s} {rate:>8s} {avg_c:>10s} {avg_t:>10s}")
    
    # Best config recommendation
    best_config = max(config_stats.items(),
                      key=lambda x: (x[1]["success"], x[1]["avg_chars"] / max(x[1]["total"], 1)))
    print(f"\n>> Recommended config: {best_config[0]} "
          f"(success={best_config[1]['success']}/{best_config[1]['total']})")
    
    # Save results
    out = output_path("test_results_wsj_optimization.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "total_tests": len(all_results),
            "config_stats": config_stats,
            "results": [
                {
                    "url": r.url,
                    "config": r.config.name,
                    "success": r.success,
                    "content_length": r.content_length,
                    "elapsed_ms": r.elapsed_ms,
                    "title": r.title,
                    "error": r.error,
                    "preview": r.preview[:200],
                }
                for r in all_results
            ],
        }, f, indent=2, ensure_ascii=False)
    
    print(f"\nResults saved to: {out}")


if __name__ == "__main__":
    asyncio.run(main())

