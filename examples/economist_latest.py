# -*- coding: utf-8 -*-
"""抓取经济学人 Economist 最新 5 篇文章并提取正文.

策略: 从 Weekly Edition 页面 (/weeklyedition/) 提取文章链接，
      再用 SmartFetcher (BPC + CloakBrowser + Trafilatura) 逐篇抓取正文。
"""

import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from article_reader import SmartFetcher
from article_reader.fetchers.dynamic import DynamicFetcher

# 非文章 URL 关键词 (topic/landing/nav 页面)
NON_ARTICLE = [
    "/subscribe", "/login", "/auth", "/topics/", "/#",
    "/weeklyedition/archive", "/podcasts", "/newsletters", "/video",
    "/audio/", "/special-reports", "/technology-quarterly",
    "/interactive/", "/schools-brief", "/essay", "/insider",
    "/my-account", "/manage-account", "/economics-a-to-z",
]


async def main():
    async with SmartFetcher() as f:
        # ---- 1) BPC 覆盖确认 ----
        sites = [s for s in f.supported_sites if "economist" in s.lower()]
        print(f"BPC 支持的 economist 站点: {len(sites)} 个 → {sites}")

        # ---- 2) 从 Weekly Edition 提取文章链接 ----
        print("\n>>> 访问 Weekly Edition 提取最新文章链接...")
        df = DynamicFetcher(pool_size=1, engine="auto")
        await df.start()

        slot = None
        page = None
        articles = []

        try:
            slot = await df._pool.acquire()
            page = await slot.context.new_page()

            await page.goto("https://www.economist.com/weeklyedition/",
                           wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(12000)

            pg_title = await page.title()
            print(f"  页面标题: {pg_title}")

            all_hrefs = await page.evaluate("""() => {
                return [...document.querySelectorAll('a[href]')].map(a => ({
                    href: a.href,
                    text: (a.textContent || '').trim()
                }));
            }""")

            # 过滤: 有文字标题 + economist.com + 非导航页面
            seen = set()
            for h in all_hrefs:
                href = h["href"]
                text = h["text"]
                if not href or "economist.com" not in href:
                    continue
                if not text or len(text) < 15:
                    continue  # 跳过无标题或太短的
                if any(s in href for s in NON_ARTICLE):
                    continue
                u = href.split("?")[0].split("#")[0]
                # 必须有明显的文章路径深度
                parts = [p for p in u.split("/") if p]
                if len(parts) < 5:
                    continue
                if u not in seen:
                    seen.add(u)
                    articles.append(u)

            # 去重并保留最早出现的 (top of page 优先级高)
            print(f"  总链接数: {len(all_hrefs)}, 文章候选: {len(articles)}")
            for i, a in enumerate(articles[:10]):
                print(f"    {i+1}) {a}")
            articles = articles[:5]

        finally:
            if page:
                await page.close()
            if slot:
                await df._pool.release(slot)
            await df.shutdown()

        if not articles:
            print("\n  [FAIL] 无法提取文章链接")
            return

        # ---- 3) 逐篇抓取正文 ----
        print(f"\n>>> 抓取 {len(articles)} 篇文章正文...\n")
        results = []
        for i, url in enumerate(articles, 1):
            section = url.split("economist.com/")[1].split("/")[0]
            print(f"  [{i}/{len(articles)}] [{section}] {url[:100]}...")
            try:
                r = await f.fetch(url)
                results.append(r)
                status = "OK" if r.success else "FAIL"
                t = (r.title or "(no title)")[:70]
                detail = f"{r.length:,} chars" if r.success else str(r.error)[:60]
                print(f"    {status}: {t} ({detail}, {r.elapsed_ms:.0f}ms)")
            except Exception as e:
                from article_reader.fetchers import FetchResult
                results.append(FetchResult(url=url, content_type="error", success=False, error=str(e)))
                print(f"    ERROR: {e}")

        # ---- 4) 输出 ----
        print(f"\n{'='*70}")
        ok = sum(1 for r in results if r.success)
        total_chars = sum(r.length for r in results)
        print(f"  经济学人最新 {len(articles)} 篇文章")
        print(f"  成功: {ok}/{len(results)}  |  总字符: {total_chars:,}")
        print(f"{'='*70}\n")

        for i, r in enumerate(results, 1):
            print(f"{'─'*70}")
            status = "✅" if r.success else "❌"
            print(f"  #{i} {status}  {r.title or '(无标题)'}")
            section = r.url.split("economist.com/")[1].split("/")[0] if r.url else ""
            print(f"  栏目: {section}  |  URL: {r.url}")
            print(f"  方法: {r.method}  |  长度: {r.length:,} chars  |  耗时: {r.elapsed_ms:.0f}ms")
            if r.author:
                print(f"  作者: {r.author}")
            if r.date:
                print(f"  日期: {r.date}")
            if r.success:
                preview = r.content[:600].replace("\n", "\n    ")
                print(f"  正文:\n    {preview}")
            else:
                print(f"  错误: {r.error}")
            print()

        print(f"{'='*70}")
        print(f"总计: {ok}/{len(results)} 成功, {total_chars:,} 字符")


if __name__ == "__main__":
    asyncio.run(main())
