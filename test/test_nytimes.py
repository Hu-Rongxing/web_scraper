# -*- coding: utf-8 -*-
"""
测试 NYTimes 不同 URL，找到有效的文章链接
"""
import sys
import asyncio
import os
from path_setup import add_src_to_path

# 设置编码
if sys.platform == 'win32':
    os.system('chcp 65001 > nul')
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

add_src_to_path()
from web_scraper import ArticleReader

# 尝试不同类型的 NYTimes URL
test_urls = [
    # 最近的文章 (通用格式)
    "https://www.nytimes.com/2024/12/15/business/economy/federal-reserve-interest-rates.html",
    "https://www.nytimes.com/2024/11/20/technology/artificial-intelligence.html",
    "https://www.nytimes.com/2024/10/10/us/politics/election-campaign.html",
    # 主页
    "https://www.nytimes.com/",
]

async def main():
    print("=" * 60)
    print("NYTimes URL 测试")
    print("=" * 60)

    async with ArticleReader(pool_size=1, use_trafilatura=True) as reader:
        for i, url in enumerate(test_urls, 1):
            print(f"\n[{i}/{len(test_urls)}] 测试: {url}")
            print("-" * 60)

            try:
                result = await reader.read(url)

                print(f"  标题: {result.title[:70] if result.title else 'N/A'}")
                print(f"  成功: {result.success}")
                print(f"  方法: {result.method}")
                print(f"  长度: {result.length:,} 字符")
                print(f"  耗时: {result.elapsed_ms:.0f}ms")

                if result.success and result.length > 500:
                    print("  ✓ 找到有效 URL!")
                    print("\n  内容预览:")
                    print(f"  {result.content[:200].replace(chr(10), ' ')}...")
                    break
                elif result.error:
                    print(f"  ✗ 错误: {result.error[:100]}")
                else:
                    print("  ⚠ 内容太短，继续尝试...")

            except Exception as e:
                print(f"  ✗ 异常: {str(e)[:100]}")

if __name__ == "__main__":
    asyncio.run(main())
