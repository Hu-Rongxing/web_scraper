# -*- coding: utf-8 -*-
"""抓取腾讯新闻首页最新 5 篇文章并提取正文."""

import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import requests
import trafilatura

from article_reader.fetchers.dynamic import DynamicFetcher
from article_reader.fetchers import FetchResult


async def main():
    print(">>> 启动 DynamicFetcher...")
    df = DynamicFetcher(pool_size=1, engine="auto")
    await df.start()

    slot = None
    page = None
    articles = []
    page_title = ""

    try:
        slot = await df._pool.acquire()
        page = await slot.context.new_page()

        # ---- 1) 打开腾讯新闻首页 ----
        print(">>> 访问 news.qq.com 首页...")
        await page.goto("https://news.qq.com/", wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(10000)

        page_title = await page.title()
        print(f"  页面标题: {page_title}")

        # ---- 2) 提取文章链接 (腾讯新闻常见格式) ----
        # news.qq.com 是 SPA，链接在渲染后的 DOM 中
        links = await page.evaluate("""() => {
            const hrefs = [];
            document.querySelectorAll('a[href]').forEach(a => {
                const h = a.href;
                // 腾讯新闻文章 URL 特征: /rain/a/ 或 /omn/ 或 /article/
                if (h && (h.includes('news.qq.com/rain/a/') ||
                          h.includes('news.qq.com/omn/') ||
                          h.includes('new.qq.com/rain/a/') ||
                          h.includes('new.qq.com/omn/'))) {
                    hrefs.push(h);
                }
            });
            // 如果太少，扩大范围
            if (hrefs.length < 5) {
                document.querySelectorAll('a[href]').forEach(a => {
                    const h = a.href;
                    if (h && (h.includes('qq.com') && (
                        h.includes('/article/') || h.includes('/a/20') || h.includes('/detail/')
                    ))) {
                        hrefs.push(h);
                    }
                });
            }
            return [...new Set(hrefs)];
        }""")

        # 去重 + 排序
        seen = set()
        for href in links:
            u = href.split("?")[0].split("#")[0]
            if u not in seen and len(u.split("/")) >= 5:
                seen.add(u)
                articles.append(u)

        print(f"  找到 {len(articles)} 篇文章链接")
        for i, a in enumerate(articles[:10]):
            print(f"    {i+1}) {a}")
        articles = articles[:5]

    finally:
        if page:
            await page.close()
        if slot:
            await df._pool.release(slot)

    # ---- 3) 如果首页不够，走热搜/要闻 API ----
    if len(articles) < 5:
        print("\n>>> 首页链接不足，补充从腾讯新闻 API 获取...")
        api_articles = await _fetch_from_api(df)
        # 合并
        existing_urls = set(articles)
        for a in api_articles:
            if a not in existing_urls:
                articles.append(a)
                existing_urls.add(a)
        articles = articles[:5]

    if not articles:
        print("  [FAIL] 无法获取文章链接。")
        await df.shutdown()
        return

    print(f"\n>>> 抓取 {len(articles)} 篇文章正文...\n")

    # ---- 4) 逐篇用 DynamicFetcher 渲染后提取正文 ----
    results = []
    for i, url in enumerate(articles, 1):
        print(f"  [{i}/{len(articles)}] {url[:100]}...")
        try:
            r = await _fetch_article(df, url)
            results.append(r)
            status = "OK" if r.success else "FAIL"
            preview_len = f"{r.length:,} chars" if r.success else str(r.error)[:60]
            title = (r.title or "(no title)")[:60]
            print(f"    {status}: {title} ({preview_len}, {r.elapsed_ms:.0f}ms)")
        except Exception as e:
            results.append(FetchResult(url=url, content_type="error", success=False, error=str(e)))
            print(f"    ERROR: {e}")

    await df.shutdown()

    # ---- 5) 输出 ----
    print(f"\n{'='*70}")
    ok = sum(1 for r in results if r.success)
    total_chars = sum(r.length for r in results)
    print(f"  腾讯新闻最新 {len(articles)} 篇文章")
    print(f"  成功: {ok}/{len(results)}  |  总字符: {total_chars:,}")
    print(f"{'='*70}\n")

    for i, r in enumerate(results, 1):
        print(f"{'─'*70}")
        status = "✅" if r.success else "❌"
        print(f"  #{i} {status}  {r.title or '(无标题)'}")
        print(f"  {r.url}")
        print(f"  方法: {r.method}  |  长度: {r.length:,} chars  |  耗时: {r.elapsed_ms:.0f}ms")
        if r.author:
            print(f"  来源: {r.author}")
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


async def _fetch_from_api(df) -> list[str]:
    """通过腾讯新闻 API 获取最新文章链接 (不需要浏览器)."""
    articles = []
    try:
        # 腾讯新闻要闻频道 API
        api_urls = [
            ("https://i.news.qq.com/trpc.qqnews_web.pc_base_srv.base_http_proxy/"
             "NinjaPageContentSync?pull_urls=news_top_2018"),
            "https://r.inews.qq.com/gw/event/hot_ranking_list?page_size=20",
        ]
        for api_url in api_urls:
            try:
                resp = requests.get(api_url, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/130.0.0.0",
                    "Referer": "https://news.qq.com/",
                }, timeout=15)
                if resp.status_code == 200:
                    data = resp.json()
                    # 从 API 中提取文章 URL
                    found = _extract_urls_from_json(data)
                    if found:
                        articles.extend(found)
                        break
            except Exception:
                continue

        # 去重
        seen = set()
        unique = []
        for u in articles:
            if u not in seen:
                seen.add(u)
                unique.append(u)
        print(f"  API 获取: {len(unique)} 篇")
        return unique[:5]
    except Exception as e:
        print(f"  API 异常: {e}")
        return []


def _extract_urls_from_json(obj) -> list[str]:
    """递归从 JSON 中提取 news.qq.com 文章 URL."""
    urls = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in ("url", "cms_id", "article_id", "link") and isinstance(v, str):
                if "news.qq.com" in v or "new.qq.com" in v:
                    urls.append(v)
            urls.extend(_extract_urls_from_json(v))
    elif isinstance(obj, list):
        for item in obj:
            urls.extend(_extract_urls_from_json(item))
    elif isinstance(obj, str):
        if ("news.qq.com/rain/a/" in obj or
            "new.qq.com/rain/a/" in obj or
            "news.qq.com/omn/" in obj or
            "new.qq.com/omn/" in obj):
            urls.append(obj)
    return urls


async def _fetch_article(df, url: str) -> FetchResult:
    """用 DynamicFetcher 渲染页面后 extract 正文."""
    import time
    start = time.time()

    slot = None
    page = None
    try:
        slot = await df._pool.acquire()
        page = await slot.context.new_page()

        await page.goto(url, wait_until="domcontentloaded", timeout=45000)
        await page.wait_for_timeout(5000)

        # 提取标题
        title = await page.evaluate("""() => {
            const h1 = document.querySelector('h1');
            if (h1) return h1.textContent.trim();
            const titleTag = document.querySelector('title');
            return titleTag ? titleTag.textContent.trim() : '';
        }""")

        # 提取来源/日期
        meta_text = await page.evaluate("""() => {
            const source = document.querySelector('.source, .author, [class*="source"], [class*="author"], .article-source');
            const time = document.querySelector('.time, .date, [class*="time"], [class*="date"], .article-time');
            let parts = [];
            if (source) parts.push(source.textContent.trim());
            if (time) parts.push(time.textContent.trim());
            return parts.join(' | ');
        }""")

        # 正文 HTML
        article_html = await page.evaluate("""() => {
            const selectors = [
                '.content-article', '#ArticleContent', '.article-content',
                'article', '[class*="article-content"]', '[class*="article_body"]',
                '.Cnt-Main-Article-QQ', '#Cnt-Main-Article-QQ',
                '#article_detail', '.detail-content', '[class*="content"]',
            ];
            for (const sel of selectors) {
                const el = document.querySelector(sel);
                if (el && el.textContent.trim().length > 200) return el.outerHTML;
            }
            // 兜底: 找正文最长的 div
            const divs = [...document.querySelectorAll('div')];
            let best = null, bestLen = 0;
            for (const d of divs) {
                const len = d.textContent.trim().length;
                if (len > bestLen && len > 500) { best = d; bestLen = len; }
            }
            return best ? best.outerHTML : document.body.innerHTML;
        }""")

        # Trafilatura 提取
        raw_html = f"<html><head><title>{title}</title></head><body>{article_html}</body></html>"
        content = trafilatura.extract(raw_html, include_comments=False, include_tables=False)
        if not content or len(content) < 100:
            # fallback: 纯文本
            content = await page.evaluate("""() => {
                const sel = '.content-article, #ArticleContent, .article-content, article, [class*="article-content"]';
                const el = document.querySelector(sel);
                return el ? el.textContent.trim() : document.body.textContent.trim().substring(0, 10000);
            }""")

        length = len(content) if content else 0

        return FetchResult(
            url=url,
            final_url=page.url,
            title=title,
            content=content or "",
            author=meta_text,
            length=length,
            content_type="article" if length > 200 else "error",
            method="dynamic:trafilatura",
            success=length > 100,
            elapsed_ms=(time.time() - start) * 1000,
        )

    except Exception as e:
        return FetchResult(
            url=url, content_type="error", success=False,
            error=str(e), elapsed_ms=(time.time() - start) * 1000,
        )
    finally:
        if page:
            await page.close()
        if slot:
            await df._pool.release(slot)


if __name__ == "__main__":
    asyncio.run(main())
