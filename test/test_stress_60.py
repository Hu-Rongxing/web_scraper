# -*- coding: utf-8 -*-
"""
60 站点并发压力测试 - 同时读取 60 个不同站点

与 test_performance.py 的区别:
  - test_performance.py: 循环复用 4 个 URL, 测请求数吞吐
  - test_stress_60.py:   60 个【不同站点同时并发】, 压测浏览器池
                         在高并发下的排队 / 复用 / 健康检查 / 资源稳定性

用法:
  python test_stress_60.py                    # 60 站点, 池=10, 并发上限=15
  python test_stress_60.py --pool 15          # 浏览器池 15 实例
  python test_stress_60.py --max-concurrent 20  # 并发上限 20
  python test_stress_60.py --count 30         # 只测前 30 个站点
  python test_stress_60.py --headless         # 无头模式

注意:
  60 个浏览器页面同时打开非常吃内存 (每个 Chromium 页面 ~150-300MB)。
  浏览器池会把 60 个请求排队到 pool 个实例上, 通过 max-concurrent
  信号量进一步限流, 避免一次性打开 60 个页面拖垮机器。
"""

import sys
import os
import asyncio
import time
import statistics
from path_setup import add_src_to_path

# Windows 控制台 UTF-8
if sys.platform == "win32":
    os.system("chcp 65001 > nul")
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

add_src_to_path()

from web_scraper import ArticleReader  # noqa: E402


# ============================================================
# 60 个站点 (主页 URL — 永不过期, 适合稳定压测池负载)
# 全部来自 BPC 支持的 939 个域名, 覆盖美/英/欧/科技/学术/财经
# ============================================================

SITES = [
    # --- 美国主流 (1-12) ---
    ("WSJ", "https://www.wsj.com/"),
    ("New York Times", "https://www.nytimes.com/"),
    ("Bloomberg", "https://www.bloomberg.com/"),
    ("Washington Post", "https://www.washingtonpost.com/"),
    ("USA Today", "https://www.usatoday.com/"),
    ("Los Angeles Times", "https://www.latimes.com/"),
    ("Chicago Tribune", "https://www.chicagotribune.com/"),
    ("Boston Globe", "https://www.bostonglobe.com/"),
    ("The Atlantic", "https://www.theatlantic.com/"),
    ("The New Yorker", "https://www.newyorker.com/"),
    ("Politico", "https://www.politico.com/"),
    ("The Hill", "https://thehill.com/"),
    # --- 财经 / 商业 (13-24) ---
    ("Financial Times", "https://www.ft.com/"),
    ("The Economist", "https://www.economist.com/"),
    ("Barron's", "https://www.barrons.com/"),
    ("Business Insider", "https://www.businessinsider.com/"),
    ("Forbes", "https://www.forbes.com/"),
    ("Fortune", "https://fortune.com/"),
    ("CNBC", "https://www.cnbc.com/"),
    ("MarketWatch", "https://www.marketwatch.com/"),
    ("The Information", "https://www.theinformation.com/"),
    ("Quartz", "https://qz.com/"),
    ("Harvard Business Review", "https://hbr.org/"),
    ("Inc.", "https://www.inc.com/"),
    # --- 科技 (25-34) ---
    ("Wired", "https://www.wired.com/"),
    ("MIT Tech Review", "https://www.technologyreview.com/"),
    ("Ars Technica", "https://arstechnica.com/"),
    ("The Verge", "https://www.theverge.com/"),
    ("Wired UK", "https://www.wired.co.uk/"),
    ("VentureBeat", "https://venturebeat.com/"),
    ("IEEE Spectrum", "https://spectrum.ieee.org/"),
    ("TechCrunch", "https://techcrunch.com/"),
    ("Engadget", "https://www.engadget.com/"),
    ("ZDNet", "https://www.zdnet.com/"),
    # --- 科学 / 学术 (35-42) ---
    ("Nature", "https://www.nature.com/"),
    ("Scientific American", "https://www.scientificamerican.com/"),
    ("Science", "https://www.science.org/"),
    ("New Scientist", "https://www.newscientist.com/"),
    ("National Geographic", "https://www.nationalgeographic.com/"),
    ("Smithsonian", "https://www.smithsonianmag.com/"),
    ("PNAS", "https://www.pnas.org/"),
    ("Cell", "https://www.cell.com/"),
    # --- 英国 / 欧洲 (43-52) ---
    ("The Times (UK)", "https://www.thetimes.com/"),
    ("The Telegraph", "https://www.telegraph.co.uk/"),
    ("The Guardian", "https://www.theguardian.com/"),
    ("The Independent", "https://www.independent.co.uk/"),
    ("BBC", "https://www.bbc.com/"),
    ("Der Spiegel", "https://www.spiegel.de/"),
    ("Le Monde", "https://www.lemonde.fr/"),
    ("Die Zeit", "https://www.zeit.de/"),
    ("El País", "https://elpais.com/"),
    ("The Irish Times", "https://www.irishtimes.com/"),
    # --- 地区 / 其他 (53-60) ---
    ("Seattle Times", "https://www.seattletimes.com/"),
    ("The Atlantic Daily", "https://www.theatlantic.com/world/"),
    ("Foreign Policy", "https://foreignpolicy.com/"),
    ("Foreign Affairs", "https://www.foreignaffairs.com/"),
    ("The New Republic", "https://newrepublic.com/"),
    ("Vox", "https://www.vox.com/"),
    ("Slate", "https://slate.com/"),
    ("Vanity Fair", "https://www.vanityfair.com/"),
]


class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    RESET = "\033[0m"
    BOLD = "\033[1m"


def header(text):
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'=' * 80}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{text.center(80)}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'=' * 80}{Colors.RESET}\n")


def parse_args():
    args = {"pool": 10, "max_concurrent": 15, "count": 60,
            "headless": False, "batch": 0}
    for i, a in enumerate(sys.argv):
        if a == "--pool" and i + 1 < len(sys.argv):
            args["pool"] = int(sys.argv[i + 1])
        elif a == "--max-concurrent" and i + 1 < len(sys.argv):
            args["max_concurrent"] = int(sys.argv[i + 1])
        elif a == "--count" and i + 1 < len(sys.argv):
            args["count"] = int(sys.argv[i + 1])
        elif a == "--batch" and i + 1 < len(sys.argv):
            # 分批模式: 每批 N 个站点跑完后再起下一批 (池排空, 消除长尾等待)
            args["batch"] = int(sys.argv[i + 1])
        elif a == "--headless":
            args["headless"] = True
    return args


async def read_one(reader, semaphore, idx, name, url, results, done_counter, total):
    """读取单个站点, 信号量限流并发数。"""
    t_enqueue = time.monotonic()
    async with semaphore:
        t_start = time.monotonic()
        wait_ms = (t_start - t_enqueue) * 1000  # 在信号量处排队的时间
        try:
            result = await reader.read(url)
            elapsed = (time.monotonic() - t_start) * 1000
            ok = result.success
            results.append({
                "idx": idx, "name": name, "url": url,
                "success": ok,
                "elapsed_ms": result.elapsed_ms or elapsed,
                "wait_ms": wait_ms,
                "length": result.length,
                "method": result.method,
                "error": result.error,
            })
            done_counter[0] += 1
            mark = f"{Colors.GREEN}✓{Colors.RESET}" if ok else f"{Colors.RED}✗{Colors.RESET}"
            print(f"  [{done_counter[0]:2d}/{total}] {mark} {name:<22} "
                  f"{result.elapsed_ms:>7.0f}ms  wait={wait_ms:>6.0f}ms  "
                  f"{result.length:>6,}字符  {result.method}")
        except Exception as e:
            elapsed = (time.monotonic() - t_start) * 1000
            results.append({
                "idx": idx, "name": name, "url": url,
                "success": False, "elapsed_ms": elapsed, "wait_ms": wait_ms,
                "length": 0, "method": "exception", "error": str(e)[:200],
            })
            done_counter[0] += 1
            print(f"  [{done_counter[0]:2d}/{total}] {Colors.RED}✗{Colors.RESET} "
                  f"{name:<22} 异常: {str(e)[:60]}")


def pct(sorted_list, p):
    if not sorted_list:
        return 0
    k = min(int(len(sorted_list) * p), len(sorted_list) - 1)
    return sorted_list[k]


def print_summary(results, wall_time, pool_stats, cfg):
    header("60 站点并发压测 — 结果汇总")

    total = len(results)
    ok = [r for r in results if r["success"]]
    fail = [r for r in results if not r["success"]]
    times = sorted(r["elapsed_ms"] for r in results)
    waits = sorted(r["wait_ms"] for r in results)
    lengths = [r["length"] for r in ok]

    print(f"{Colors.BOLD}配置:{Colors.RESET}")
    print(f"  浏览器池: {cfg['pool']} 实例   并发上限: {cfg['max_concurrent']}   "
          f"Headless: {cfg['headless']}")

    print(f"\n{Colors.BOLD}总览:{Colors.RESET}")
    print(f"  站点总数: {total}")
    print(f"  {Colors.GREEN}成功: {len(ok)} ({len(ok)/total*100:.1f}%){Colors.RESET}")
    print(f"  {Colors.RED}失败: {len(fail)} ({len(fail)/total*100:.1f}%){Colors.RESET}")
    print(f"  墙钟总耗时: {wall_time:.1f}s")
    print(f"  吞吐量: {total/wall_time:.2f} 站点/秒")

    if times:
        print(f"\n{Colors.BOLD}单站点响应时间 (含池排队):{Colors.RESET}")
        print(f"  平均: {statistics.mean(times):.0f}ms")
        print(f"  中位(P50): {statistics.median(times):.0f}ms")
        print(f"  P95: {pct(times, 0.95):.0f}ms")
        print(f"  P99: {pct(times, 0.99):.0f}ms")
        print(f"  最快: {times[0]:.0f}ms   最慢: {times[-1]:.0f}ms")

    if waits:
        print(f"\n{Colors.BOLD}信号量排队等待:{Colors.RESET}")
        print(f"  平均: {statistics.mean(waits):.0f}ms   "
              f"P95: {pct(waits, 0.95):.0f}ms   最长: {waits[-1]:.0f}ms")

    if lengths:
        print(f"\n{Colors.BOLD}内容长度 (成功站点):{Colors.RESET}")
        print(f"  平均: {statistics.mean(lengths):,.0f}字符   "
              f"中位: {statistics.median(lengths):,.0f}字符   "
              f"最长: {max(lengths):,}字符")

    # 提取方法分布
    methods = {}
    for r in ok:
        key = r["method"].split(":")[0] if r["method"] else "unknown"
        methods[key] = methods.get(key, 0) + 1
    if methods:
        print(f"\n{Colors.BOLD}提取方法分布:{Colors.RESET}")
        for m, c in sorted(methods.items(), key=lambda x: -x[1]):
            print(f"  {m}: {c} ({c/len(ok)*100:.0f}%)")

    if fail:
        print(f"\n{Colors.BOLD}{Colors.RED}失败站点 ({len(fail)}):{Colors.RESET}")
        for r in fail:
            reason = r["error"][:50] if r["error"] else "内容过短/空"
            print(f"  {Colors.RED}✗{Colors.RESET} {r['name']:<22} {reason}")

    print(f"\n{Colors.BOLD}浏览器池最终状态:{Colors.RESET}")
    print(f"  总 slots: {pool_stats.get('total_slots', '?')}   "
          f"已处理页面: {pool_stats.get('total_pages_served', '?')}   "
          f"崩溃: {pool_stats.get('crashed', '?')}")


async def main():
    cfg = parse_args()
    sites = SITES[: cfg["count"]]
    total = len(sites)

    header(f"Web Scraper — {total} 站点并发压力测试")
    print(f"  浏览器池: {cfg['pool']} 实例")
    print(f"  并发上限: {cfg['max_concurrent']} (信号量限流)")
    print(f"  目标站点: {total} 个")
    print(f"  Headless: {cfg['headless']}")
    print(f"\n  {Colors.YELLOW}注意: {total} 个请求将排队到 {cfg['pool']} 个浏览器实例，"
          f"信号量限制同时最多 {cfg['max_concurrent']} 个在跑。{Colors.RESET}")

    t0 = time.monotonic()
    results = []
    done_counter = [0]

    async with ArticleReader(
        pool_size=cfg["pool"],
        headless=cfg["headless"],
        use_trafilatura=True,
    ) as reader:
        print(f"\n{Colors.GREEN}✓ ArticleReader 已启动{Colors.RESET}  "
              f"BPC v{reader._plugin_manager._get_current_version()}  "
              f"支持 {len(reader._plugin_manager.get_supported_domains())} 域名\n")

        semaphore = asyncio.Semaphore(cfg["max_concurrent"])

        if cfg["batch"] > 0:
            # 分批模式: 每批跑完后再起下一批, 任一时刻只有 batch 个请求争抢资源
            bsize = cfg["batch"]
            num_batches = (total + bsize - 1) // bsize
            print(f"  {Colors.CYAN}分批模式: {num_batches} 批 × {bsize} 站/批"
                  f"{Colors.RESET}\n")
            for b in range(num_batches):
                chunk = sites[b * bsize:(b + 1) * bsize]
                print(f"{Colors.BOLD}{Colors.BLUE}── 第 {b+1}/{num_batches} 批 "
                      f"({len(chunk)} 站) ──{Colors.RESET}")
                batch_tasks = [
                    read_one(reader, semaphore, b * bsize + j, name, url,
                             results, done_counter, total)
                    for j, (name, url) in enumerate(chunk)
                ]
                await asyncio.gather(*batch_tasks)
        else:
            tasks = [
                read_one(reader, semaphore, i, name, url, results, done_counter, total)
                for i, (name, url) in enumerate(sites)
            ]
            await asyncio.gather(*tasks)

        wall_time = time.monotonic() - t0
        pool_stats = reader.stats().get("pool", {})

    print_summary(results, wall_time, pool_stats, cfg)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}⚠ 用户中断{Colors.RESET}")
