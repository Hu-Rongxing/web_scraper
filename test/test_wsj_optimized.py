# -*- coding: utf-8 -*-
"""
WSJ optimization test - simplified.
Uses the standard P4 pipeline but captures HTML for post-hoc comparison:
1. trafilatura vs readability-lxml extraction quality
2. RSS vs direct URL effectiveness
"""

import asyncio
import sys
import time
import json
import re
from pathlib import Path
from datetime import datetime
from output_paths import output_path

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, str(Path(__file__).parent.parent))

from article_reader import SmartFetcher


WSJ_TEST_URLS = [
    # RSS mod (more content-friendly)
    {"name": "wsj_currencies_rss", "url": "https://www.wsj.com/finance/currencies/asia-currency-ai-energy-8d4f4cb4?mod=rss_markets_main"},
    {"name": "wsj_energy_oil_rss", "url": "https://www.wsj.com/business/energy-oil/why-oil-prices-havent-shot-through-the-roofyet-bca1f60b?mod=rss_markets_main"},
    {"name": "wsj_credit_card_rss", "url": "https://www.wsj.com/finance/investing/america-has-a-credit-card-problem-just-not-the-one-you-think-da0859be?mod=rss_markets_main"},
    
    # Direct (no RSS mod)
    {"name": "wsj_currencies_dir", "url": "https://www.wsj.com/finance/currencies/asia-currency-ai-energy-8d4f4cb4"},
    {"name": "wsj_energy_oil_dir", "url": "https://www.wsj.com/business/energy-oil/why-oil-prices-havent-shot-through-the-roofyet-bca1f60b"},
    {"name": "wsj_credit_card_dir", "url": "https://www.wsj.com/finance/investing/america-has-a-credit-card-problem-just-not-the-one-you-think-da0859be"},
]


def extract_readability(html: str) -> dict:
    """Extract content using readability-lxml."""
    try:
        from readability import Document
        doc = Document(html)
        content_html = doc.summary()
        content = re.sub(r'<[^>]+>', ' ', content_html)
        content = re.sub(r'\s+', ' ', content).strip()
        return {"title": doc.title() or "", "content": content, "method": "readability"}
    except Exception as e:
        return {"title": "", "content": "", "method": f"readability_error:{e}"}


def extract_trafilatura(html: str, url: str = "") -> dict:
    """Extract content using trafilatura."""
    try:
        import trafilatura
        content = trafilatura.extract(
            html, url=url,
            include_links=False, include_images=False,
            include_formatting=False, include_comments=False,
            deduplicate=True,
        )
        metadata = trafilatura.extract_metadata(html, default_url=url)
        title = metadata.title if metadata and metadata.title else ""
        return {
            "title": title or "",
            "content": (content or "").strip(),
            "author": metadata.author if metadata else None,
            "date": metadata.date if metadata else None,
            "method": "trafilatura",
        }
    except Exception as e:
        return {"title": "", "content": "", "method": f"trafilatura_error:{e}"}


def extract_bare_html(html: str) -> dict:
    """Bare minimum: strip all HTML tags."""
    content = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.S | re.I)
    content = re.sub(r'<style[^>]*>.*?</style>', '', content, flags=re.S | re.I)
    content = re.sub(r'<[^>]+>', ' ', content)
    content = re.sub(r'\s+', ' ', content).strip()
    title = ""
    m = re.search(r'<title[^>]*>(.+?)</title>', html, re.I | re.S)
    if m:
        title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
    return {"title": title, "content": content, "method": "bare_html"}


async def main():
    print(f"\n{'='*80}")
    print(f"WSJ Optimization Test - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*80}\n")
    
    results = []
    
    async with SmartFetcher() as fetcher:
        for i, tc in enumerate(WSJ_TEST_URLS, 1):
            name = tc["name"]
            url = tc["url"]
            print(f"\n[{i}/{len(WSJ_TEST_URLS)}] {name}")
            print(f"  URL: {url[:90]}...")
            
            try:
                t0 = time.monotonic()
                result = await fetcher.fetch(url)
                elapsed = time.monotonic() - t0
                
                if not result.success:
                    print(f"  [FAIL] P{result.meta.get('pipeline_level',0)}: {result.error[:80]}")
                    results.append({
                        "name": name, "url": url, "success": False,
                        "elapsed_s": round(elapsed, 1),
                        "error": result.error,
                    })
                    continue
                
                pipeline = result.meta.get("pipeline_level", 0)
                method = result.method
                
                print(f"  [OK] P{pipeline} | {elapsed:.0f}s | trafilatura={len(result.content)} chars")
                
                # Post-hoc comparison - extract from raw HTML if available
                html = result.html
                if html:
                    traf = extract_trafilatura(html, url)
                    read = extract_readability(html)
                    bare = extract_bare_html(html)
                    
                    print(f"  Post-hoc: trafilatura={len(traf['content'])} readability={len(read['content'])} bare={len(bare['content'])}")
                    print(f"  Title: traf='{traf['title'][:60]}' read='{read['title'][:60]}'")
                    
                    r = {
                        "name": name,
                        "url": url,
                        "success": True,
                        "pipeline": pipeline,
                        "method": method,
                        "elapsed_s": round(elapsed, 1),
                        "pipeline_content_len": result.length,
                        "pipeline_title": result.title[:100] if result.title else "",
                        "trafilatura_len": len(traf["content"]),
                        "trafilatura_title": traf["title"][:100],
                        "readability_len": len(read["content"]),
                        "readability_title": read["title"][:100],
                        "bare_html_len": len(bare["content"]),
                        "html_len": len(html),
                        "pipeline_preview": result.content[:150] if result.content else "",
                        "readability_preview": read["content"][:150],
                        "trafilatura_preview": traf["content"][:150],
                    }
                else:
                    r = {
                        "name": name, "url": url, "success": True,
                        "pipeline": pipeline, "method": method,
                        "elapsed_s": round(elapsed, 1),
                        "pipeline_content_len": result.length,
                        "pipeline_title": result.title[:100] if result.title else "",
                        "error": "No HTML captured for comparison",
                    }
                
                results.append(r)
                
            except Exception as e:
                print(f"  [EXCEPTION] {str(e)[:100]}")
                results.append({
                    "name": name, "url": url, "success": False,
                    "error": str(e)[:200],
                })
            
            await asyncio.sleep(1)
    
    # ============================================================
    # Summary
    # ============================================================
    print(f"\n\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")
    
    ok = [r for r in results if r.get("success")]
    fail = [r for r in results if not r.get("success")]
    print(f"Total: {len(results)} | OK: {len(ok)} | Fail: {len(fail)}")
    
    if ok:
        print(f"\n{'Name':<25s} {'P':>3s} {'Time':>6s} {'Traf':>8s} {'Read':>8s} {'Bare':>8s} {'Title'}")
        print(f"{'-'*25} {'-'*3} {'-'*6} {'-'*8} {'-'*8} {'-'*8} {'-'*40}")
        
        for r in ok:
            p = r.get("pipeline", "?")
            t = f"{r['elapsed_s']:.0f}s"
            tlen = str(r.get("trafilatura_len", "?"))
            rlen = str(r.get("readability_len", "?"))
            blen = str(r.get("bare_html_len", "?"))
            title = (r.get("pipeline_title") or "")[:40]
            print(f"{r['name']:<25s} {str(p):>3s} {t:>6s} {tlen:>8s} {rlen:>8s} {blen:>8s} {title}")
        
        # Best extractor analysis
        traf_total = sum(r.get("trafilatura_len", 0) for r in ok)
        read_total = sum(r.get("readability_len", 0) for r in ok)
        print(f"\nTrafilatura total: {traf_total} chars | Readability total: {read_total} chars")
        
        if read_total > traf_total:
            print(">> readability-lxml yields MORE content than trafilatura for WSJ")
        else:
            print(">> trafilatura yields MORE content than readability-lxml for WSJ")
    
    if fail:
        print("\nFailed:")
        for r in fail:
            print(f"  - {r['name']}: {r.get('error', 'unknown')[:80]}")
    
    # Save
    out = output_path("test_results_wsj_optimized.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "total": len(results),
            "ok": len(ok),
            "fail": len(fail),
            "results": results,
        }, f, indent=2, ensure_ascii=False)
    
    print(f"\nResults: {out}")


if __name__ == "__main__":
    asyncio.run(main())
