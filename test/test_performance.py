# -*- coding: utf-8 -*-
"""
性能压测脚本 - 测试 web_scraper 的性能和稳定性

用法:
  python test_performance.py                    # 默认压测
  python test_performance.py --duration 300     # 压测 5 分钟
  python test_performance.py --requests 100     # 压测 100 次请求
  python test_performance.py --concurrent 5     # 并发数 5
"""

import sys
import asyncio
import time
from path_setup import add_src_to_path
import statistics
import os

# 设置 Windows 控制台 UTF-8 编码
if sys.platform == 'win32':
    os.system('chcp 65001 > nul')
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# 确保能找到 web_scraper 包
add_src_to_path()

from web_scraper import ArticleReader

# 测试 URL 池 (选择稳定的网站)
TEST_URLS = [
    "https://www.wsj.com/articles/suspected-sabotage-of-deep-sea-cable-triggers-first-nato-led-response-337119ba",
    "https://www.forbes.com/sites/forbestechcouncil/2025/01/15/the-future-of-ai/",
    "https://www.businessinsider.com/personal-finance/how-to-invest-money",
    "https://www.wired.com/story/artificial-intelligence-future/",
]

class PerformanceStats:
    """性能统计收集器"""
    def __init__(self):
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.response_times = []
        self.content_lengths = []
        self.errors = []
        self.start_time = time.time()

    def record_success(self, elapsed_ms: float, content_length: int):
        self.total_requests += 1
        self.successful_requests += 1
        self.response_times.append(elapsed_ms)
        self.content_lengths.append(content_length)

    def record_failure(self, error: str):
        self.total_requests += 1
        self.failed_requests += 1
        self.errors.append(error)

    def elapsed(self) -> float:
        return time.time() - self.start_time

    def requests_per_second(self) -> float:
        elapsed = self.elapsed()
        return self.total_requests / elapsed if elapsed > 0 else 0

    def print_summary(self):
        print("\n" + "=" * 80)
        print("性能压测结果汇总".center(80))
        print("=" * 80 + "\n")

        print(f"总请求数: {self.total_requests}")
        print(f"成功: {self.successful_requests} ({self.successful_requests/self.total_requests*100:.1f}%)")
        print(f"失败: {self.failed_requests} ({self.failed_requests/self.total_requests*100:.1f}%)")
        print(f"总耗时: {self.elapsed():.2f}s")
        print(f"吞吐量: {self.requests_per_second():.2f} req/s")

        if self.response_times:
            print("\n响应时间统计:")
            print(f"  平均: {statistics.mean(self.response_times):.0f}ms")
            print(f"  中位: {statistics.median(self.response_times):.0f}ms")
            print(f"  P95: {sorted(self.response_times)[int(len(self.response_times)*0.95)]:.0f}ms")
            print(f"  P99: {sorted(self.response_times)[int(len(self.response_times)*0.99)]:.0f}ms")
            print(f"  最小: {min(self.response_times):.0f}ms")
            print(f"  最大: {max(self.response_times):.0f}ms")

        if self.content_lengths:
            print("\n内容长度统计:")
            print(f"  平均: {statistics.mean(self.content_lengths):,.0f} 字符")
            print(f"  中位: {statistics.median(self.content_lengths):,.0f} 字符")

        if self.errors:
            print("\n错误类型分布:")
            error_counts = {}
            for e in self.errors:
                # 只取前 50 个字符
                e_short = e[:50]
                error_counts[e_short] = error_counts.get(e_short, 0) + 1
            for error, count in sorted(error_counts.items(), key=lambda x: x[1], reverse=True)[:5]:
                print(f"  {error}: {count}次")

async def stress_test_worker(
    reader: ArticleReader,
    stats: PerformanceStats,
    worker_id: int,
    target_requests: int,
    semaphore: asyncio.Semaphore
):
    """压测工作协程"""
    request_count = 0

    while request_count < target_requests:
        async with semaphore:
            url = TEST_URLS[request_count % len(TEST_URLS)]

            try:
                result = await reader.read(url)

                if result.success:
                    stats.record_success(result.elapsed_ms, result.length)
                    print(f"[Worker-{worker_id}] ✓ {request_count+1}/{target_requests} | "
                          f"{result.elapsed_ms:.0f}ms | {result.length} chars")
                else:
                    stats.record_failure(result.error or "未知错误")
                    print(f"[Worker-{worker_id}] ✗ {request_count+1}/{target_requests} | "
                          f"失败: {result.error or '未知'}")

            except Exception as e:
                stats.record_failure(str(e))
                print(f"[Worker-{worker_id}] ✗ {request_count+1}/{target_requests} | 异常: {e}")

        request_count += 1

async def run_stress_test(
    duration_seconds: int = None,
    total_requests: int = None,
    concurrent_workers: int = 3,
    max_concurrent_requests: int = 5,
):
    """运行压测"""
    print("=" * 80)
    print("Web Scraper 性能压测".center(80))
    print("=" * 80 + "\n")

    if duration_seconds:
        print(f"模式: 时长压测 ({duration_seconds}秒)")
        # 估算请求数 (假设每个请求 10 秒)
        total_requests = duration_seconds * concurrent_workers // 10
    else:
        total_requests = total_requests or 20
        print(f"模式: 请求数压测 ({total_requests} 次)")

    print(f"并发工作者: {concurrent_workers}")
    print(f"最大并发请求: {max_concurrent_requests}")
    print(f"测试 URL 池: {len(TEST_URLS)} 个")
    print()

    stats = PerformanceStats()

    async with ArticleReader(pool_size=5, use_trafilatura=True) as reader:
        print("✓ ArticleReader 已启动")
        print(f"  BPC 版本: {reader._plugin_manager._get_current_version()}")
        print("  浏览器池: 5 实例\n")

        # 创建信号量限制并发
        semaphore = asyncio.Semaphore(max_concurrent_requests)

        # 每个 worker 处理的请求数
        requests_per_worker = total_requests // concurrent_workers

        # 启动所有 worker
        tasks = [
            stress_test_worker(reader, stats, i, requests_per_worker, semaphore)
            for i in range(concurrent_workers)
        ]

        # 等待所有任务完成
        await asyncio.gather(*tasks)

        # 打印汇总
        stats.print_summary()

        # 打印池状态
        pool_stats = reader.stats()
        print("\n浏览器池状态:")
        print(f"  总 slots: {pool_stats['pool']['total_slots']}")
        print(f"  已处理页面: {pool_stats['pool']['total_pages_served']}")
        print(f"  崩溃次数: {pool_stats['pool']['crashed']}")

def parse_args():
    """解析命令行参数"""
    args = {
        "duration": None,
        "requests": None,
        "concurrent": 3,
        "max_concurrent": 5,
    }

    for i, arg in enumerate(sys.argv):
        if arg == "--duration" and i + 1 < len(sys.argv):
            try:
                args["duration"] = int(sys.argv[i + 1])
            except ValueError:
                pass
        if arg == "--requests" and i + 1 < len(sys.argv):
            try:
                args["requests"] = int(sys.argv[i + 1])
            except ValueError:
                pass
        if arg == "--concurrent" and i + 1 < len(sys.argv):
            try:
                args["concurrent"] = int(sys.argv[i + 1])
            except ValueError:
                pass
        if arg == "--max-concurrent" and i + 1 < len(sys.argv):
            try:
                args["max_concurrent"] = int(sys.argv[i + 1])
            except ValueError:
                pass

    return args

async def main():
    """主函数"""
    args = parse_args()

    try:
        await run_stress_test(
            duration_seconds=args["duration"],
            total_requests=args["requests"],
            concurrent_workers=args["concurrent"],
            max_concurrent_requests=args["max_concurrent"],
        )
    except KeyboardInterrupt:
        print("\n\n⚠ 用户中断")
    except Exception as e:
        print(f"\n\n✗ 致命错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
