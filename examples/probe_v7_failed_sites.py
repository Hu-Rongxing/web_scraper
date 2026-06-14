# -*- coding: utf-8 -*-
"""Probe representative URLs that have failed in monitor_v7.

This script is intentionally standalone inside web_scraper. It does not import
monitor_v7 code or read monitor_v7 config at runtime; the sample URLs are copied
here as external test inputs.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from path_setup import add_src_to_path

add_src_to_path()

from web_scraper import PipelineManager  # noqa: E402


SAMPLES = [
    {
        "site": "wsj",
        "url": "https://www.wsj.com/finance/currencies/asia-currency-ai-energy-8d4f4cb4?mod=rss_markets_main",
        "known_issue": "Dow Jones reader 401/451 or Datadome challenge; BPC browser may be required.",
    },
    {
        "site": "wsj_cn",
        "url": "https://cn.wsj.com/articles/china-markets-economy-2026",
        "known_issue": "WSJ CN often returns 401 captcha-delivery or reader warning shells.",
    },
    {
        "site": "marketwatch",
        "url": "https://www.marketwatch.com/story/gold-has-tumbled-during-the-iran-war-exposing-a-massive-myth-about-geopolitical-risk-15bd2c94?mod=mw_rss_topstories",
        "known_issue": "Original detail and Jina reader often return 401/451 challenge shells.",
    },
    {
        "site": "economist",
        "url": "https://www.economist.com/business/2026/06/10/american-capitalism-is-run-by-millionaires-not-billionaires",
        "known_issue": "Public reader/origin can expose trial teaser only.",
    },
    {
        "site": "project_syndicate",
        "url": "https://www.project-syndicate.org/commentary/us-debt-dollar-confidence-global-economy-by-kenneth-rogoff-2026-06",
        "known_issue": "Public pages often expose Poool/paywall preview only.",
    },
    {
        "site": "omfif",
        "url": "https://www.omfif.org/2026/06/the-ecbs-inflation-challenge/",
        "known_issue": "Origin Cloudflare 403; some r.jina.ai URL shapes work.",
    },
    {
        "site": "hkej",
        "url": "https://www.hkej.com/instantnews/article/id/4080000/",
        "known_issue": "Cloudflare 403; reader fallback may be the only lightweight route.",
    },
    {
        "site": "spglobal",
        "url": "https://www.spglobal.com/market-intelligence/en/news-insights/articles/2026/6/sample-investor-news",
        "known_issue": "Investor detail URLs can return 403 locally.",
    },
    {
        "site": "fitch",
        "url": "https://www.fitchratings.com/research/sovereigns/armenia-election-signals-policy-continuity-amid-lingering-geopolitical-risks-10-06-2026",
        "known_issue": "Premium report/API shells may not expose public full text.",
    },
    {
        "site": "reuters",
        "url": "https://www.reuters.com/world/us/",
        "known_issue": "Origin may block; TradingView mirror works for selected newsml items.",
    },
    {
        "site": "swift",
        "url": "https://www.swift.com/news-events/news",
        "known_issue": "Origin timeouts; reader/list source can be more stable.",
    },
    {
        "site": "ftchinese",
        "url": "https://www.ftchinese.com/story/001102000",
        "known_issue": "Local Chinese preview paywall markers; linked original may be needed.",
    },
]


@dataclass
class ProbeRow:
    site: str
    url: str
    known_issue: str
    success: bool
    method: str
    final_url: str
    elapsed_ms: float
    title: str
    content_length: int
    error: str
    meta: dict


async def probe_one(manager: PipelineManager, sample: dict, *, timeout_sec: float, skip_browser: bool) -> ProbeRow:
    started = time.monotonic()
    result = await asyncio.wait_for(
        manager.fetch(
            sample["url"],
            timeout=min(timeout_sec, 10),
            level_timeout_sec=min(timeout_sec, 10),
            http_timeout_sec=min(timeout_sec, 8),
            bypass_method_timeout_sec=min(timeout_sec, 4),
            skip_browser=skip_browser,
        ),
        timeout=timeout_sec,
    )
    return ProbeRow(
        site=sample["site"],
        url=sample["url"],
        known_issue=sample["known_issue"],
        success=result.success,
        method=result.method,
        final_url=result.final_url,
        elapsed_ms=result.elapsed_ms or ((time.monotonic() - started) * 1000),
        title=result.title[:160] if result.title else "",
        content_length=result.length,
        error=result.error or "",
        meta=result.meta,
    )


async def run(samples: list[dict], output_dir: Path, *, timeout_sec: float, skip_browser: bool) -> list[ProbeRow]:
    output_dir.mkdir(parents=True, exist_ok=True)
    rows: list[ProbeRow] = []
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    site_slug = "-".join(sample["site"] for sample in samples[:4])
    if len(samples) > 4:
        site_slug += f"-plus{len(samples) - 4}"
    json_path = output_dir / f"v7_failed_site_probe_{stamp}_{site_slug}.json"
    md_path = output_dir / f"v7_failed_site_probe_{stamp}_{site_slug}.md"
    async with AsyncPipelineManager() as manager:
        for index, sample in enumerate(samples, start=1):
            print(f"[{index}/{len(samples)}] {sample['site']} {sample['url']}")
            try:
                row = await probe_one(manager, sample, timeout_sec=timeout_sec, skip_browser=skip_browser)
            except asyncio.TimeoutError:
                row = ProbeRow(
                    site=sample["site"],
                    url=sample["url"],
                    known_issue=sample["known_issue"],
                    success=False,
                    method="probe_timeout",
                    final_url="",
                    elapsed_ms=timeout_sec * 1000,
                    title="",
                    content_length=0,
                    error=f"probe timed out after {timeout_sec:.0f}s",
                    meta={},
                )
            except Exception as exc:
                row = ProbeRow(
                    site=sample["site"],
                    url=sample["url"],
                    known_issue=sample["known_issue"],
                    success=False,
                    method="probe_exception",
                    final_url="",
                    elapsed_ms=0.0,
                    title="",
                    content_length=0,
                    error=str(exc),
                    meta={},
                )
            rows.append(row)
            status = "OK" if row.success else "FAIL"
            print(f"  {status} method={row.method} chars={row.content_length} error={row.error[:120]}")
            write_reports(rows, json_path, md_path)

    print(f"JSON: {json_path}")
    print(f"Markdown: {md_path}")
    return rows


def write_reports(rows: list[ProbeRow], json_path: Path, md_path: Path) -> None:
    json_path.write_text(json.dumps([asdict(row) for row in rows], ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(rows), encoding="utf-8")


class AsyncPipelineManager:
    def __init__(self):
        self.manager = PipelineManager()

    async def __aenter__(self) -> PipelineManager:
        await self.manager.start()
        return self.manager

    async def __aexit__(self, *args) -> None:
        await self.manager.shutdown()


def render_markdown(rows: list[ProbeRow]) -> str:
    lines = [
        "# v7 Failure Sample Probe",
        "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "| Site | Status | Method | Chars | Error |",
        "|---|---:|---|---:|---|",
    ]
    for row in rows:
        status = "OK" if row.success else "FAIL"
        error = (row.error or "").replace("|", "\\|")[:140]
        lines.append(f"| {row.site} | {status} | {row.method} | {row.content_length} | {error} |")
    lines.append("")
    lines.append("## Details")
    lines.append("")
    for row in rows:
        lines.extend([
            f"### {row.site}",
            f"- URL: {row.url}",
            f"- Known issue: {row.known_issue}",
            f"- Success: {row.success}",
            f"- Method: {row.method}",
            f"- Final URL: {row.final_url}",
            f"- Content length: {row.content_length}",
            f"- Error: {row.error}",
            "",
        ])
    return "\n".join(lines)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", action="append", help="Only probe selected site id; can be repeated.")
    parser.add_argument("--output-dir", default="docs/probe-results", help="Directory for probe reports.")
    parser.add_argument("--timeout-sec", type=float, default=25.0, help="Per-site timeout.")
    parser.add_argument("--with-browser", action="store_true", help="Allow browser pool fallback paths.")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    selected = SAMPLES
    if args.site:
        wanted = set(args.site)
        selected = [sample for sample in SAMPLES if sample["site"] in wanted]
    asyncio.run(run(selected, Path(args.output_dir), timeout_sec=args.timeout_sec, skip_browser=not args.with_browser))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
