# -*- coding: utf-8 -*-
"""
调试 NYTimes 页面结构，找出正确的内容选择器
"""
import sys
import asyncio
import os
from pathlib import Path

if sys.platform == 'win32':
    os.system('chcp 65001 > nul')
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from playwright.async_api import async_playwright

async def debug_nytimes():
    """调试 NYTimes 页面结构"""

    # 使用一个已知存在的 NYTimes 文章 URL
    # 注意：这个 URL 可能需要更新
    test_url = "https://www.nytimes.com/"

    print("=" * 80)
    print("NYTimes 页面结构调试")
    print("=" * 80)
    print(f"\n测试 URL: {test_url}\n")

    playwright = await async_playwright().start()

    try:
        # 启动浏览器
        browser = await playwright.chromium.launch(headless=False)
        context = await browser.new_context(
            viewport={'width': 1280, 'height': 900},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        page = await context.new_page()

        print("🌐 正在加载页面...")
        await page.goto(test_url, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(5)  # 等待渲染

        print("✓ 页面加载完成\n")

        # 尝试不同的选择器
        selectors_to_test = [
            "section[name='articleBody']",
            "article#story",
            "article",
            ".StoryBodyCompanionColumn",
            "[data-testid='article-body']",
            ".css-at9mc1",  # NYTimes 常用的 CSS 类
            "main article",
            "main section",
            ".story-wrapper",
            "#story",
            "[role='article']",
        ]

        print("🔍 测试选择器:\n")

        working_selectors = []

        for selector in selectors_to_test:
            try:
                element = await page.query_selector(selector)
                if element:
                    text = await element.inner_text()
                    text_length = len(text.strip())

                    if text_length > 100:
                        print(f"  ✓ {selector:50} → {text_length:6,} 字符")
                        working_selectors.append({
                            'selector': selector,
                            'length': text_length,
                            'preview': text.strip()[:100]
                        })
                    else:
                        print(f"  ⚠ {selector:50} → {text_length:6} 字符 (太短)")
                else:
                    print(f"  ✗ {selector:50} → 未找到")
            except Exception as e:
                print(f"  ✗ {selector:50} → 错误: {str(e)[:30]}")

        # 显示最佳选择器
        if working_selectors:
            print("\n" + "=" * 80)
            print("推荐的选择器 (按内容长度排序):")
            print("=" * 80)

            working_selectors.sort(key=lambda x: x['length'], reverse=True)

            for i, item in enumerate(working_selectors[:3], 1):
                print(f"\n[{i}] {item['selector']}")
                print(f"    长度: {item['length']:,} 字符")
                print(f"    预览: {item['preview']}...")
        else:
            print("\n⚠ 没有找到有效的选择器")

        # 保存页面截图用于调试
        screenshot_path = "nytimes_debug.png"
        await page.screenshot(path=screenshot_path, full_page=False)
        print(f"\n📸 页面截图已保存: {screenshot_path}")

        # 保存 HTML 用于离线分析
        html_content = await page.content()
        html_path = "nytimes_debug.html"
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"💾 HTML 已保存: {html_path}")

        await browser.close()

    finally:
        await playwright.stop()

if __name__ == "__main__":
    asyncio.run(debug_nytimes())
