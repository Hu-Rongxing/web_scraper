# -*- coding: utf-8 -*-
"""
全面测试脚本 - 测试多个主流付费新闻网站

用法:
  python test_comprehensive.py                 # 测试所有网站
  python test_comprehensive.py --quick         # 快速测试 (仅测试 5 个网站)
  python test_comprehensive.py --site wsj      # 仅测试特定网站
  python test_comprehensive.py --concurrent 3  # 并发数 (默认 2)
"""

import sys
import asyncio
import time
from pathlib import Path
from typing import List
import statistics
import os

# 设置 Windows 控制台 UTF-8 编码
if sys.platform == 'win32':
    os.system('chcp 65001 > nul')
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# 确保能找到 article_reader 包
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from article_reader import ArticleReader

# ============================================================
# 测试站点配置
# ============================================================

TEST_SITES = {
    # 主流美国媒体
    "wsj": {
        "name": "Wall Street Journal",
        "url": "https://www.wsj.com/articles/suspected-sabotage-of-deep-sea-cable-triggers-first-nato-led-response-337119ba",
        "paywall": True,
        "priority": 1,
    },
    "nytimes": {
        "name": "New York Times",
        "url": "https://www.nytimes.com/",  # 使用主页代替，因为具体文章 URL 经常过期
        "paywall": True,
        "priority": 1,
    },
    "bloomberg": {
        "name": "Bloomberg",
        "url": "https://www.bloomberg.com/news/articles/2025-01-15/trump-s-pick-for-treasury-secretary-bessent-faces-senate-hearing",
        "paywall": True,
        "priority": 1,
    },
    "ft": {
        "name": "Financial Times",
        "url": "https://www.ft.com/content/e7b3f8a0-8f3d-4c3e-b5a1-2d3e4f5a6b7c",
        "paywall": True,
        "priority": 2,
    },
    "washingtonpost": {
        "name": "Washington Post",
        "url": "https://www.washingtonpost.com/politics/2025/01/15/trump-agenda-congress/",
        "paywall": True,
        "priority": 2,
    },

    # 商业 & 科技媒体
    "economist": {
        "name": "The Economist",
        "url": "https://www.economist.com/leaders/2025/01/09/artificial-intelligence-is-losing-hype-and-gaining-traction",
        "paywall": True,
        "priority": 2,
    },
    "barrons": {
        "name": "Barron's",
        "url": "https://www.barrons.com/articles/stock-market-today-e77c5d8a",
        "paywall": True,
        "priority": 3,
    },
    "businessinsider": {
        "name": "Business Insider",
        "url": "https://www.businessinsider.com/personal-finance/how-to-invest-money",
        "paywall": True,
        "priority": 3,
    },
    "forbes": {
        "name": "Forbes",
        "url": "https://www.forbes.com/sites/forbestechcouncil/2025/01/15/the-future-of-ai/",
        "paywall": False,  # 部分免费
        "priority": 3,
    },
    "fortune": {
        "name": "Fortune",
        "url": "https://fortune.com/2025/01/15/ceo-daily-openings/",
        "paywall": True,
        "priority": 3,
    },

    # 杂志 & 深度报道
    "theatlantic": {
        "name": "The Atlantic",
        "url": "https://www.theatlantic.com/magazine/archive/2025/02/artificial-intelligence-chatgpt/",
        "paywall": True,
        "priority": 2,
    },
    "newyorker": {
        "name": "The New Yorker",
        "url": "https://www.newyorker.com/magazine/2025/01/20/the-future-of-work",
        "paywall": True,
        "priority": 2,
    },
    "wired": {
        "name": "Wired",
        "url": "https://www.wired.com/story/artificial-intelligence-future/",
        "paywall": True,
        "priority": 3,
    },

    # 科学 & 学术
    "nature": {
        "name": "Nature",
        "url": "https://www.nature.com/articles/d41586-024-00001-0",
        "paywall": True,
        "priority": 3,
    },
    "scientificamerican": {
        "name": "Scientific American",
        "url": "https://www.scientificamerican.com/article/the-science-of-artificial-intelligence/",
        "paywall": True,
        "priority": 3,
    },

    # 英国媒体
    "thetimes": {
        "name": "The Times (UK)",
        "url": "https://www.thetimes.com/article/artificial-intelligence-jobs-future-work",
        "paywall": True,
        "priority": 3,
    },
    "telegraph": {
        "name": "The Telegraph",
        "url": "https://www.telegraph.co.uk/business/2025/01/15/uk-economy/",
        "paywall": True,
        "priority": 3,
    },

    # 地区性报纸
    "seattletimes": {
        "name": "Seattle Times",
        "url": "https://www.seattletimes.com/business/technology/",
        "paywall": True,
        "priority": 4,
    },
    "latimes": {
        "name": "Los Angeles Times",
        "url": "https://www.latimes.com/california/story/2025-01-15/",
        "paywall": True,
        "priority": 4,
    },
    "bostonglobe": {
        "name": "Boston Globe",
        "url": "https://www.bostonglobe.com/2025/01/15/metro/",
        "paywall": True,
        "priority": 4,
    },
}

# 颜色输出
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def print_header(text: str):
    """打印标题"""
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'=' * 80}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{text.center(80)}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'=' * 80}{Colors.RESET}\n")

def print_site_header(site_name: str):
    """打印站点标题"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}>>> {site_name}{Colors.RESET}")
    print(f"{Colors.BLUE}{'-' * 60}{Colors.RESET}")

def print_success(text: str):
    """成功消息"""
    print(f"{Colors.GREEN}✓ {text}{Colors.RESET}")

def print_error(text: str):
    """错误消息"""
    print(f"{Colors.RED}✗ {text}{Colors.RESET}")

def print_warning(text: str):
    """警告消息"""
    print(f"{Colors.YELLOW}⚠ {text}{Colors.RESET}")

def print_info(text: str):
    """信息消息"""
    print(f"  {text}")

async def test_single_site(reader: ArticleReader, site_key: str, site_info: dict) -> dict:
    """测试单个网站"""
    print_site_header(site_info["name"])
    print_info(f"URL: {site_info['url']}")

    result_dict = {
        "site": site_key,
        "name": site_info["name"],
        "success": False,
        "error": None,
        "elapsed_ms": 0,
        "content_length": 0,
        "method": "",
        "title": "",
    }

    try:
        result = await reader.read(site_info["url"])

        result_dict.update({
            "success": result.success,
            "error": result.error,
            "elapsed_ms": result.elapsed_ms,
            "content_length": result.length,
            "method": result.method,
            "title": result.title,
        })

        if result.success:
            print_success("读取成功")
            print_info(f"标题: {result.title[:60]}{'...' if len(result.title) > 60 else ''}")
            print_info(f"方法: {result.method}")
            print_info(f"长度: {result.length:,} 字符")
            print_info(f"耗时: {result.elapsed_ms:.0f}ms")

            if result.content:
                preview = result.content[:200].replace("\n", " ")
                print_info(f"预览: {preview}...")
        else:
            print_error("读取失败")
            if result.error:
                print_error(f"错误: {result.error[:100]}")

    except Exception as e:
        print_error(f"异常: {str(e)[:100]}")
        result_dict["error"] = str(e)

    return result_dict

async def test_concurrent_sites(reader: ArticleReader, sites: List[tuple], max_concurrent: int = 2) -> List[dict]:
    """并发测试多个网站"""
    semaphore = asyncio.Semaphore(max_concurrent)

    async def test_with_semaphore(site_key: str, site_info: dict):
        async with semaphore:
            return await test_single_site(reader, site_key, site_info)

    tasks = [test_with_semaphore(key, info) for key, info in sites]
    return await asyncio.gather(*tasks)

def print_summary(results: List[dict], total_time: float):
    """打印测试汇总"""
    print_header("测试汇总")

    total = len(results)
    successful = sum(1 for r in results if r["success"])
    failed = total - successful

    # 成功率
    success_rate = (successful / total * 100) if total > 0 else 0

    print(f"{Colors.BOLD}总计:{Colors.RESET} {total} 个网站")
    print_success(f"成功: {successful} ({success_rate:.1f}%)")
    if failed > 0:
        print_error(f"失败: {failed} ({100 - success_rate:.1f}%)")

    # 性能统计
    if successful > 0:
        successful_results = [r for r in results if r["success"]]
        times = [r["elapsed_ms"] for r in successful_results]
        lengths = [r["content_length"] for r in successful_results]

        print(f"\n{Colors.BOLD}性能统计:{Colors.RESET}")
        print_info(f"总耗时: {total_time:.2f}s")
        print_info(f"平均响应: {statistics.mean(times):.0f}ms")
        print_info(f"中位响应: {statistics.median(times):.0f}ms")
        print_info(f"最快: {min(times):.0f}ms")
        print_info(f"最慢: {max(times):.0f}ms")

        print(f"\n{Colors.BOLD}内容统计:{Colors.RESET}")
        print_info(f"平均长度: {statistics.mean(lengths):,.0f} 字符")
        print_info(f"中位长度: {statistics.median(lengths):,.0f} 字符")
        print_info(f"最短: {min(lengths):,} 字符")
        print_info(f"最长: {max(lengths):,} 字符")

        # 方法分布
        methods = {}
        for r in successful_results:
            method = r["method"].split(":")[0]  # 去掉 selector 详情
            methods[method] = methods.get(method, 0) + 1

        print(f"\n{Colors.BOLD}提取方法分布:{Colors.RESET}")
        for method, count in sorted(methods.items(), key=lambda x: x[1], reverse=True):
            print_info(f"{method}: {count} ({count/successful*100:.1f}%)")

    # 失败详情
    if failed > 0:
        print(f"\n{Colors.BOLD}{Colors.RED}失败站点:{Colors.RESET}")
        for r in results:
            if not r["success"]:
                print_error(f"{r['name']}: {r['error'][:80] if r['error'] else '未知错误'}")

def parse_args():
    """解析命令行参数"""
    args = {
        "quick": "--quick" in sys.argv,
        "site": None,
        "concurrent": 2,
    }

    # 查找 --site 参数
    for i, arg in enumerate(sys.argv):
        if arg == "--site" and i + 1 < len(sys.argv):
            args["site"] = sys.argv[i + 1].lower()
        if arg == "--concurrent" and i + 1 < len(sys.argv):
            try:
                args["concurrent"] = int(sys.argv[i + 1])
            except ValueError:
                pass

    return args

async def main():
    """主测试流程"""
    args = parse_args()

    print_header("Article Reader 全面测试")

    # 选择要测试的网站
    sites_to_test = []

    if args["site"]:
        # 测试特定网站
        if args["site"] in TEST_SITES:
            sites_to_test = [(args["site"], TEST_SITES[args["site"]])]
            print(f"测试模式: 单站点 ({TEST_SITES[args['site']]['name']})")
        else:
            print_error(f"未知站点: {args['site']}")
            print(f"可用站点: {', '.join(TEST_SITES.keys())}")
            return
    elif args["quick"]:
        # 快速测试 - 优先级 1 的网站
        sites_to_test = [(k, v) for k, v in TEST_SITES.items() if v["priority"] == 1]
        print(f"测试模式: 快速 (仅 {len(sites_to_test)} 个优先级 1 网站)")
    else:
        # 全面测试
        sites_to_test = list(TEST_SITES.items())
        print(f"测试模式: 全面 (所有 {len(sites_to_test)} 个网站)")

    print_info(f"并发数: {args['concurrent']}")
    print_info("浏览器池: 3 实例")
    print_info("Trafilatura: 启用")

    # 启动 ArticleReader
    t_start = time.time()

    async with ArticleReader(pool_size=3, use_trafilatura=True) as reader:
        print(f"\n{Colors.GREEN}✓ ArticleReader 已启动{Colors.RESET}")
        print_info(f"BPC 版本: {reader._plugin_manager._get_current_version()}")
        print_info(f"BPC 支持站点: {len(reader._plugin_manager.get_supported_domains())} 个")

        # 运行测试
        results = await test_concurrent_sites(reader, sites_to_test, max_concurrent=args["concurrent"])

        # 打印汇总
        total_time = time.time() - t_start
        print_summary(results, total_time)

        # 池状态
        print(f"\n{Colors.BOLD}浏览器池状态:{Colors.RESET}")
        stats = reader.stats()
        print_info(f"总 slots: {stats['pool']['total_slots']}")
        print_info(f"使用中: {stats['pool']['in_use']}")
        print_info(f"已处理页面: {stats['pool']['total_pages_served']}")
        print_info(f"崩溃: {stats['pool']['crashed']}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}用户中断{Colors.RESET}")
    except Exception as e:
        print(f"\n\n{Colors.RED}致命错误: {e}{Colors.RESET}")
        import traceback
        traceback.print_exc()
