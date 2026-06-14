# -*- coding: utf-8 -*-
"""
article_reader 测试脚本

用法:
  python test_reader.py                          # 默认测试 WSJ
  python test_reader.py <article-url>            # 指定文章
  python test_reader.py --list                   # 列出支持的站点
  python test_reader.py --list bloomberg         # 搜索支持的站点
  python test_reader.py --stats                  # 查看池状态
"""

import sys
import asyncio
from path_setup import add_src_to_path

# 确保能找到 article_reader 包
add_src_to_path()

from article_reader import ArticleReader, PluginManager


async def main():
    if "--list" in sys.argv:
        pm = PluginManager()
        if not pm.verify_extension():
            print("⚠️  BPC 扩展未找到")
            return

        query = None
        for arg in sys.argv[1:]:
            if arg != "--list" and not arg.startswith("-"):
                query = arg
                break

        sites = pm.get_supported_domains()
        if query:
            sites = [s for s in sites if query.lower() in s]
            print(f"BPC 支持站点 (匹配 '{query}'): {len(sites)}")
        else:
            print(f"BPC 支持站点总数: {len(sites)}")

        for s in sites[:50]:
            print(f"  {s}")
        if len(sites) > 50:
            print(f"  ... 还有 {len(sites) - 50} 个")
        return

    if "--stats" in sys.argv:
        # 需要已启动的 reader
        pass

    # ---- 测试读取 ----
    test_urls = [
        "https://www.wsj.com/articles/suspected-sabotage-of-deep-sea-cable-triggers-first-nato-led-response-337119ba",
    ]

    # 如果命令行传了 URL, 用那个
    for arg in sys.argv[1:]:
        if arg.startswith("http"):
            test_urls = [arg]
            break

    async with ArticleReader(pool_size=1, use_trafilatura=True) as reader:
        print("=" * 60)
        print("ArticleReader 测试")
        print(f"  池大小: {reader._pool_size}")
        print(f"  BPC 版本: {reader._plugin_manager._get_current_version()}")
        print(f"  BPC 站点数: {len(reader._plugin_manager.get_supported_domains())}")
        print("=" * 60)

        for url in test_urls:
            print(f"\n>>> 读取: {url}")
            result = await reader.read(url)

            print(f"  标题: {result.title}")
            print(f"  方法: {result.method}")
            print(f"  长度: {result.length:,} 字符")
            print(f"  耗时: {result.elapsed_ms:.0f}ms")
            print(f"  Paywall: {result.paywall}")
            print(f"  成功: {result.success}")
            if result.error:
                print(f"  错误: {result.error}")

            if result.content:
                # 打印前 500 字符
                preview = result.content[:500].replace("\n", "\n  ")
                print("\n  --- 内容预览 ---")
                print(f"  {preview}")
                print(f"  --- (共 {result.length:,} 字符) ---")

        print(f"\n{'=' * 60}")
        print("池状态:", reader.stats())
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
