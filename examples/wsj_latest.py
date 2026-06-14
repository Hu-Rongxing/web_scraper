# -*- coding: utf-8 -*-
"""抓取 WSJ 首页最新 5 篇文章并提取正文."""

import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Windows UTF-8
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from article_reader import SmartFetcher
from article_reader.fetchers.dynamic import DynamicFetcher


async def main():
    async with SmartFetcher() as f:
        # 1) 用 DynamicFetcher 访问 WSJ 首页提取真实链接
        print(">>> 访问 WSJ 首页提取最新文章链接...")
        df = DynamicFetcher(pool_size=1, engine="auto")
        await df.start()

        slot = None
        page = None
        articles = []

        try:
            slot = await df._pool.acquire()
            page = await slot.context.new_page()

            # 拦截 paywall 相关请求
            async def block_paywall(route):
                url = route.request.url
                paywall_kw = ["piano.io", "tinypass", "/api/paywall", "/meter", "cxense"]
                if any(kw in url for kw in paywall_kw):
                    await route.abort()
                else:
                    await route.continue_()
            await page.route("**/*", block_paywall)

            await page.goto("https://www.wsj.com", wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(12000)

            # 打印页面标题确认加载成功
            pg_title = await page.title()
            print(f"  页面标题: {pg_title}")

            # 提取所有链接
            all_hrefs = await page.evaluate("""() => {
                return [...document.querySelectorAll('a[href]')].map(a => a.href);
            }""")

            print(f"  页面链接总数: {len(all_hrefs)}")

            # 调试: 打印前 30 个 wsj 链接看看格式
            wsj_links = [h for h in all_hrefs if "wsj.com" in h and h.count("/") > 3]
            print(f"  WSJ 长链接: {len(wsj_links)}")
            print("  前 10 个链接样本:")
            for i, link in enumerate(wsj_links[:10]):
                print(f"    {i+1}) {link}")

            # 过滤真实文章链接 — WSJ 文章 URL 格式多样
            seen = set()
            for href in all_hrefs:
                if not href or "wsj.com" not in href:
                    continue
                # 去参数
                u = href.split("?")[0].split("#")[0]
                if u in seen:
                    continue
                # 排除非文章类型
                skip = [
                    "/newsletters/", "/podcasts/", "/video/", "/live-coverage/",
                    "/photos/", "/graphics/", "login", "subscribe", "customercenter",
                    "wsj.com/", "/about", "/account",
                ]
                if any(s in u for s in skip):
                    continue
                # 必须是比较长的路径 (>3 段)
                parts = [p for p in u.split("/") if p]
                if len(parts) >= 5:
                    seen.add(u)
                    articles.append(u)

            print(f"  过滤后文章: {len(articles)}")
            articles = articles[:5]

        finally:
            if page:
                await page.close()
            if slot:
                await df._pool.release(slot)
            await df.shutdown()

        if not articles:
            print("\n  [FAIL] 无法从首页提取文章链接。WSJ 可能要求登录后才能看到列表。")
            print("  尝试直接搜索 WSJ 最新文章...")
            articles = await _search_wsj_articles(df)
            if not articles:
                print("  [FAIL] 也搜不到。退出。")
                return

        print(f"\n>>> 抓取 {len(articles)} 篇文章正文...\n")

        # 2) 逐篇抓取
        results = []
        for i, url in enumerate(articles, 1):
            print(f"  [{i}/{len(articles)}] {url[:90]}...")
            try:
                r = await f.fetch(url)
                results.append(r)
                status = "OK" if r.success else "FAIL"
                preview_len = f"{r.length:,} chars" if r.success else str(r.error)[:60]
                print(f"    {status}: {r.title[:60] if r.title else '(no title)'} ({preview_len}, {r.elapsed_ms:.0f}ms)")
            except Exception as e:
                from article_reader.fetchers import FetchResult
                results.append(FetchResult(url=url, content_type="error", success=False, error=str(e)))
                print(f"    ERROR: {e}")

        # 3) 输出
        print(f"\n{'='*70}")
        ok = sum(1 for r in results if r.success)
        total_chars = sum(r.length for r in results)
        print(f"  WSJ 最新 {len(articles)} 篇文章")
        print(f"  成功: {ok}/{len(results)}  |  总字符: {total_chars:,}")
        print(f"{'='*70}\n")

        for i, r in enumerate(results, 1):
            print(f"{'─'*70}")
            status = "✅" if r.success else "❌"
            print(f"  #{i} {status}  {r.title or '(无标题)'}")
            print(f"  {r.url}")
            print(f"  方法: {r.method}  |  长度: {r.length:,} chars  |  耗时: {r.elapsed_ms:.0f}ms")
            if r.author:
                print(f"  作者: {r.author}")
            if r.date:
                print(f"  日期: {r.date}")
            if r.success:
                preview = r.content[:500].replace("\n", "\n    ")
                print(f"  正文:\n    {preview}")
            else:
                print(f"  错误: {r.error}")
            print()

        print(f"{'='*70}")
        print(f"总计: {ok}/{len(results)} 成功, {total_chars:,} 字符")


async def _search_wsj_articles(df):
    """备用: 用首页提取的 Popular Articles 列表抓取."""
    slot = None
    page = None
    articles = []

    try:
        slot = await df._pool.acquire()
        page = await slot.context.new_page()

        await page.goto("https://www.wsj.com", wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(10000)

        # 尝试从 Popular/Featured 区块提取链接
        links = await page.evaluate("""() => {
            const sections = document.querySelectorAll(
                '[class*="popular"], [class*="featured"], [class*="headline"], [class*="top"], [class*="lead"]'
            );
            const hrefs = [];
            sections.forEach(s => {
                s.querySelectorAll('a[href]').forEach(a => hrefs.push(a.href));
            });
            // 也拿 h2/h3 里的链接
            document.querySelectorAll('h2 a[href], h3 a[href]').forEach(a => hrefs.push(a.href));
            return [...new Set(hrefs)].filter(h => h.includes('wsj.com'));
        }""")

        seen = set()
        for href in links:
            u = href.split("?")[0].split("#")[0]
            parts = [p for p in u.split("/") if p]
            if len(parts) >= 5 and u not in seen:
                skip = ["newsletters", "podcasts", "video", "live-coverage", "photos", "graphics",
                        "login", "subscribe", "customercenter"]
                if not any(s in u.lower() for s in skip):
                    seen.add(u)
                    articles.append(u)

        print(f"  Popular/Featured 区链接: {len(articles)}")
        return articles[:5]

    except Exception as e:
        print(f"  _search_wsj_articles error: {e}")
        return []
    finally:
        if page:
            await page.close()
        if slot:
            await df._pool.release(slot)


if __name__ == "__main__":
    asyncio.run(main())
