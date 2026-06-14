# -*- coding: utf-8 -*-
"""
优化版快速测试 - 应用所有性能优化建议

优化措施:
1. 启用 Headless 模式 (节省 15-20%)
2. 减少等待时间到 3 秒 (节省 2秒/请求)
3. 增加浏览器池到 5
4. 使用优化后的配置

用法:
  python test_optimized.py
"""

import sys
import asyncio
import time
import os
from pathlib import Path

# 设置编码
if sys.platform == 'win32':
    os.system('chcp 65001 > nul')
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# 在导入前设置优化配置
os.environ['ARTICLE_READER_WAIT_RENDER'] = '3000'  # 3秒等待
os.environ['ARTICLE_READER_HEADLESS'] = '1'        # Headless模式

from article_reader import ArticleReader

# 测试 URL
TEST_URLS = [
    ("WSJ", "https://www.wsj.com/articles/suspected-sabotage-of-deep-sea-cable-triggers-first-nato-led-response-337119ba"),
    ("NYTimes", "https://www.nytimes.com/"),
    ("Bloomberg", "https://www.bloomberg.com/"),
]

async def test_optimized():
    """运行优化测试"""
    print("=" * 80)
    print("Article Reader - 优化版测试".center(80))
    print("=" * 80)
    print("\n✨ 优化措施:")
    print("  • Headless 模式: 启用")
    print("  • 等待时间: 3 秒 (从 5 秒优化)")
    print("  • 浏览器池: 5 实例 (从 3 增加)")
    print("  • 预期性能提升: ~25-30%\n")

    results_before = []
    results_after = []

    # 第一轮: 标准配置
    print("=" * 80)
    print("第一轮: 标准配置测试".center(80))
    print("=" * 80)

    t1 = time.time()
    async with ArticleReader(pool_size=3, headless=False, use_trafilatura=True) as reader:
        for name, url in TEST_URLS:
            result = await reader.read(url)
            results_before.append({
                'name': name,
                'time': result.elapsed_ms,
                'length': result.length,
                'success': result.success
            })
            status = "✓" if result.success else "✗"
            print(f"  {status} {name:15} {result.elapsed_ms:6.0f}ms  {result.length:6,} 字符")

    total_before = time.time() - t1

    # 第二轮: 优化配置
    print("\n" + "=" * 80)
    print("第二轮: 优化配置测试".center(80))
    print("=" * 80)

    t2 = time.time()
    async with ArticleReader(pool_size=5, headless=True, use_trafilatura=True) as reader:
        for name, url in TEST_URLS:
            result = await reader.read(url)
            results_after.append({
                'name': name,
                'time': result.elapsed_ms,
                'length': result.length,
                'success': result.success
            })
            status = "✓" if result.success else "✗"
            print(f"  {status} {name:15} {result.elapsed_ms:6.0f}ms  {result.length:6,} 字符")

    total_after = time.time() - t2

    # 对比分析
    print("\n" + "=" * 80)
    print("性能对比分析".center(80))
    print("=" * 80)

    print("\n单个请求对比:")
    print(f"  {'网站':<15} {'标准配置':<12} {'优化配置':<12} {'改进':<12}")
    print("  " + "-" * 55)

    for before, after in zip(results_before, results_after):
        if before['success'] and after['success']:
            improvement = (before['time'] - after['time']) / before['time'] * 100
            print(f"  {before['name']:<15} {before['time']:>8.0f}ms  {after['time']:>8.0f}ms  {improvement:>8.1f}%")

    # 总体统计
    avg_before = sum(r['time'] for r in results_before if r['success']) / sum(1 for r in results_before if r['success'])
    avg_after = sum(r['time'] for r in results_after if r['success']) / sum(1 for r in results_after if r['success'])

    print("\n总体指标:")
    print(f"  总耗时:     {total_before:.2f}s → {total_after:.2f}s  ({(total_before-total_after)/total_before*100:+.1f}%)")
    print(f"  平均响应:   {avg_before:.0f}ms → {avg_after:.0f}ms  ({(avg_before-avg_after)/avg_before*100:+.1f}%)")

    # 结论
    print("\n" + "=" * 80)
    print("优化结论".center(80))
    print("=" * 80)

    if total_after < total_before:
        improvement = (total_before - total_after) / total_before * 100
        print(f"\n✅ 优化成功！总体性能提升 {improvement:.1f}%")
    else:
        print("\n⚠️ 优化效果不明显，可能需要调整参数")

    print("\n💡 优化建议:")
    if avg_after > 15000:
        print("  • 响应时间仍较长，建议启用代理加速")
    if improvement < 20:
        print("  • 进一步减少等待时间到 2 秒")
        print("  • 考虑禁用 Trafilatura 以提升速度")

if __name__ == "__main__":
    asyncio.run(test_optimized())
