# -*- coding: utf-8 -*-
"""
pipelines/pipeline.py — 四级管线调度器 v3.0

管线 1→2→3→4 逐级自动重试，全部失败标记站点暂不可抓取。
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlparse

from ..browser_pool import PoolA, PoolB, PoolC, BrowserSlot
from ..content_extractor import ContentExtractor
from ..models import PipelineResult
from ..proxies import (
    PipelineProxyPool,
    ResidentialRotatingPool,
    StaticBoundPool,
)
from ..config import (
    PROXY_GROUP_1,
    PROXY_GROUP_2,
    PROXY_GROUP_3A,
    PROXY_GROUP_3B,
    PAGE_GOTO_TIMEOUT,
    PAGE_WAIT_RENDER_MS,
    PIPELINE_FAILURE_SIGNALS,
    PAYWALL_DETECT_SIGNALS,
    MIN_CONTENT_LENGTH,
    logger,
)
from .anti_block import WallDetector


# ============================================================
# 管线级别枚举
# ============================================================

class PipelineLevel:
    """管线级别"""
    HTTP = 1
    BASIC_RENDER = 2
    HIGH_PROTECT = 3
    PAYWALL = 4

    @classmethod
    def all_levels(cls) -> list[int]:
        return [cls.HTTP, cls.BASIC_RENDER, cls.HIGH_PROTECT, cls.PAYWALL]

    @classmethod
    def name(cls, level: int) -> str:
        return {
            cls.HTTP: "HTTP轻量",
            cls.BASIC_RENDER: "基础渲染",
            cls.HIGH_PROTECT: "高防护",
            cls.PAYWALL: "付费墙",
        }.get(level, f"未知管线{level}")


# ============================================================
# 结果数据结构


# ============================================================

class PipelineError(Exception):
    def __init__(self, message: str, pipeline_level: int, cause: Optional[Exception] = None):
        super().__init__(message)
        self.pipeline_level = pipeline_level
        self.cause = cause


# ============================================================
# 失败站点记录
# ============================================================

@dataclass
class FailedSite:
    """四级管线全部失败的站点记录"""
    domain: str
    url: str
    failed_at: float
    reason: str
    pipeline_results: list = field(default_factory=list)
    expires_at: float = 0.0  # 过期时间戳（默认 24 小时后）

    def __post_init__(self):
        if self.expires_at == 0.0:
            self.expires_at = self.failed_at + 86400  # 24 小时后过期

    @property
    def is_expired(self) -> bool:
        return time.time() > self.expires_at


# ============================================================
# 四级管线管理器
# ============================================================

class PipelineManager:
    """
    四级管线管理器。
    管线 1→2→3→4 逐级自动重试。
    全部失败标记站点暂不可抓取。
    """

    def __init__(self):
        # 代理池
        self._proxy_g1 = PipelineProxyPool(PROXY_GROUP_1)
        self._proxy_g2 = ResidentialRotatingPool(PROXY_GROUP_2)
        self._proxy_g3a = StaticBoundPool(PROXY_GROUP_3A, pool_name="pool_b")
        self._proxy_g3b = StaticBoundPool(PROXY_GROUP_3B, pool_name="pool_c")

        # 浏览器池
        self._pool_a: Optional[PoolA] = None
        self._pool_b: Optional[PoolB] = None
        self._pool_c: Optional[PoolC] = None

        # 失败站点记录
        self._failed_sites: dict[str, FailedSite] = {}
        
        # 管线统计
        self._pipeline_stats = {
            1: {"success": 0, "failure": 0},
            2: {"success": 0, "failure": 0},
            3: {"success": 0, "failure": 0},
            4: {"success": 0, "failure": 0},
            "degradation_count": 0,  # 降级流转次数
        }

        self._started = False

    async def start(self):
        if self._started:
            return

        self._pool_a = PoolA(proxy_provider=self._proxy_g2)
        self._pool_b = PoolB(proxy_provider=self._proxy_g3a)
        self._pool_c = PoolC(proxy_provider=self._proxy_g3b)

        await asyncio.gather(
            self._pool_a.start(),
            self._pool_b.start(),
            self._pool_c.start(),
        )

        self._started = True
        logger.info("PipelineManager started: 4 pipelines with auto-degradation")

    async def shutdown(self):
        if not self._started:
            return
        await asyncio.gather(
            self._pool_a.shutdown() if self._pool_a else asyncio.sleep(0),
            self._pool_b.shutdown() if self._pool_b else asyncio.sleep(0),
            self._pool_c.shutdown() if self._pool_c else asyncio.sleep(0),
        )
        self._started = False
        logger.info("PipelineManager shutdown")

    # ============================================================
    # 主入口：逐级自动重试
    # ============================================================

    async def fetch(
        self,
        url: str,
        extract_strategy: str = "trafilatura",
        **opts,
    ) -> PipelineResult:
        """
        执行四级管线逐级自动重试。
        管线 1→2→3→4，前序失败自动流转下一级。
        全部失败标记站点暂不可抓取。
        """
        if not self._started:
            await self.start()

        domain = urlparse(url).netloc

        # 清理过期失败站点
        self._cleanup_expired_failed()

        # 检查是否已标记为不可抓取
        if domain in self._failed_sites:
            failed = self._failed_sites[domain]
            logger.warning("Site %s marked as unscrapable: %s", domain, failed.reason)
            return PipelineResult(
                url=url,
                success=False,
                error=f"Site temporarily unscrapable: {failed.reason}",
                method="blocked:failed_site",
                meta={"failed_site": True},
            )

        t0 = time.monotonic()
        pipeline_results = []

        # ---- 管线 1: HTTP 轻量 ----
        result = await self._pipeline_1_http(url, extract_strategy, **opts)
        if result.success:
            result.elapsed_ms = (time.monotonic() - t0) * 1000
            result.pipeline_level = 1
            self._pipeline_stats[1]["success"] += 1
            logger.info("Pipeline 1 success for %s (%.0fms)", url, result.elapsed_ms)
            return result
        self._pipeline_stats[1]["failure"] += 1
        pipeline_results.append(result)
        logger.info("Pipeline 1 failed for %s: %s → escalate to pipeline 2", url, result.error)

        # ---- 管线 2: 基础渲染（池 A）----
        result = await self._pipeline_2_basic_render(url, extract_strategy, **opts)
        if result.success:
            result.elapsed_ms = (time.monotonic() - t0) * 1000
            result.pipeline_level = 2
            self._pipeline_stats[2]["success"] += 1
            self._pipeline_stats["degradation_count"] += 1
            logger.info("Pipeline 2 success for %s (%.0fms)", url, result.elapsed_ms)
            return result
        self._pipeline_stats[2]["failure"] += 1
        self._pipeline_stats["degradation_count"] += 1
        pipeline_results.append(result)
        logger.info("Pipeline 2 failed for %s: %s → escalate to pipeline 3", url, result.error)

        # ---- 管线 3: 高防护（池 B）----
        result = await self._pipeline_3_high_protection(url, extract_strategy, **opts)
        if result.success and not self._detect_paywall(result):
            # 管线 3 成功且无付费墙 → 直接返回
            result.elapsed_ms = (time.monotonic() - t0) * 1000
            result.pipeline_level = 3
            self._pipeline_stats[3]["success"] += 1
            self._pipeline_stats["degradation_count"] += 1
            logger.info("Pipeline 3 success for %s (%.0fms)", url, result.elapsed_ms)
            return result
        self._pipeline_stats[3]["failure"] += 1
        self._pipeline_stats["degradation_count"] += 1
        
        # 管线 3 失败或检测到付费墙 → 流转管线 4
        if result.success and self._detect_paywall(result):
            logger.info("Pipeline 3 success but paywall detected for %s → escalate to pipeline 4", url)
        elif not result.success:
            logger.info("Pipeline 3 failed for %s: %s → escalate to pipeline 4", url, result.error)
        pipeline_results.append(result)

        # ---- 管线 4: 付费墙（池 C）----
        result = await self._pipeline_4_paywall(url, extract_strategy, **opts)
        if result.success:
            result.elapsed_ms = (time.monotonic() - t0) * 1000
            result.pipeline_level = 4
            self._pipeline_stats[4]["success"] += 1
            self._pipeline_stats["degradation_count"] += 1
            logger.info("Pipeline 4 success for %s (%.0fms)", url, result.elapsed_ms)
            return result
        self._pipeline_stats[4]["failure"] += 1
        self._pipeline_stats["degradation_count"] += 1
        pipeline_results.append(result)

        # ---- 管线 5: 反封锁突破（Archive/Cache/Reader Mode）----
        result = await self._pipeline_5_bypass(url, extract_strategy, pipeline_results, **opts)
        if result.success:
            result.elapsed_ms = (time.monotonic() - t0) * 1000
            result.pipeline_level = 5
            self._pipeline_stats["degradation_count"] += 1
            logger.info("Pipeline 5 bypass success for %s (%.0fms)", url, result.elapsed_ms)
            return result
        pipeline_results.append(result)

        # ---- 全部失败：标记站点不可抓取 ----
        elapsed = (time.monotonic() - t0) * 1000
        error_summary = "; ".join(r.error or "unknown" for r in pipeline_results)
        self._failed_sites[domain] = FailedSite(
            domain=domain,
            url=url,
            failed_at=time.time(),
            reason=error_summary[:500],
            pipeline_results=pipeline_results,
        )
        logger.error(
            "All 5 pipelines failed for %s (%.0fms) → site marked unscrapable: %s",
            domain, elapsed, error_summary[:200],
        )

        return PipelineResult(
            url=url,
            success=False,
            error=f"All 5 pipelines failed: {error_summary[:300]}",
            elapsed_ms=elapsed,
            pipeline_level=0,
            meta={"all_pipelines_failed": True, "domain": domain},
        )

    # ============================================================
    # 管线 1: HTTP 轻量（Scrapling Fetcher / curl_cffi）
    # ============================================================

    async def _pipeline_1_http(self, url: str, extract_strategy: str, **opts) -> PipelineResult:
        proxy = await self._proxy_g1.acquire()

        try:
            try:
                from scrapling import Fetcher
                fetcher = Fetcher(auto_referer=True, timeout=30)
                # Use asyncio.to_thread to avoid blocking the event loop
                resp = await asyncio.to_thread(fetcher.get, url, proxy=proxy)
                # Scrapling Fetcher Response API: .html_content 获取 HTML 文本
                html = resp.html_content if hasattr(resp, 'html_content') else resp.content if hasattr(resp, 'content') else resp.html
                final_url = str(resp.url)
                method = "scrapling_fetcher"
            except ImportError:
                import requests
                headers = {"User-Agent": "Mozilla/5.0"}
                proxies = {"http": proxy, "https": proxy} if proxy else None
                # Use asyncio.to_thread to avoid blocking the event loop
                resp = await asyncio.to_thread(
                    requests.get, url, headers=headers, proxies=proxies, timeout=30, allow_redirects=True
                )
                resp.raise_for_status()
                html = resp.text
                final_url = resp.url
                method = "requests"

            # 失败判定
            if self._is_pipeline_failure(html):
                return PipelineResult(
                    url=url, final_url=final_url, html=html,
                    method=f"pipeline1:{method}",
                    success=False,
                    error="Pipeline 1: blocked/empty/redirect to captcha",
                )

            # 内容提取
            extracted = ContentExtractor(strategy=extract_strategy).extract(html, url)

            if len(extracted.content) < MIN_CONTENT_LENGTH:
                return PipelineResult(
                    url=url, final_url=final_url, html=html,
                    method=f"pipeline1:{method}",
                    success=False,
                    error=f"Pipeline 1: content too short ({len(extracted.content)} chars)",
                )

            return PipelineResult(
                url=url, final_url=final_url,
                title=extracted.title, content=extracted.content, html=html,
                author=extracted.author, date=extracted.date,
                length=len(extracted.content), content_type="page",
                method=f"pipeline1:{method}", success=True,
            )

        except Exception as e:
            return PipelineResult(
                url=url, success=False,
                error=f"Pipeline 1 exception: {str(e)[:200]}",
                method="pipeline1:error",
            )
        finally:
            if proxy:
                await self._proxy_g1.release(proxy, success=True)

    # ============================================================
    # 管线 2: 基础渲染（池 A）
    # ============================================================

    async def _pipeline_2_basic_render(self, url: str, extract_strategy: str, **opts) -> PipelineResult:
        slot: Optional[BrowserSlot] = None
        page = None

        try:
            slot = await self._pool_a.acquire()
            page = await slot.context.new_page()
            page.set_default_timeout(PAGE_GOTO_TIMEOUT)

            html, title = await self._render_page(
                page,
                url,
                selector="article, main, .content, .app, #app",
                wait_ms=PAGE_WAIT_RENDER_MS,
                scroll_delay=0.5,
            )

            # 失败判定
            if self._is_pipeline_failure(html):
                return PipelineResult(
                    url=url, final_url=page.url, html=html, title=title,
                    method="pipeline2:pool_a",
                    success=False,
                    error="Pipeline 2: captcha/403/access denied",
                )

            extracted = ContentExtractor(strategy=extract_strategy).extract(html, url)

            if len(extracted.content) < MIN_CONTENT_LENGTH:
                return PipelineResult(
                    url=url, final_url=page.url, html=html, title=title,
                    method="pipeline2:pool_a",
                    success=False,
                    error=f"Pipeline 2: content too short ({len(extracted.content)} chars)",
                )

            return PipelineResult(
                url=url, final_url=page.url,
                title=extracted.title or title, content=extracted.content, html=html,
                author=extracted.author, date=extracted.date,
                length=len(extracted.content), content_type="page",
                method="pipeline2:pool_a", success=True,
            )

        except Exception as e:
            return PipelineResult(
                url=url, success=False,
                error=f"Pipeline 2 exception: {str(e)[:200]}",
                method="pipeline2:error",
            )
        finally:
            if page:
                try:
                    await page.close()
                except Exception:
                    pass
            if slot:
                await self._pool_a.release(slot)

    # ============================================================
    # 管线 3: 高防护主力（池 B）
    # ============================================================

    async def _pipeline_3_high_protection(self, url: str, extract_strategy: str, **opts) -> PipelineResult:
        slot: Optional[BrowserSlot] = None
        page = None

        try:
            domain = urlparse(url).netloc
            slot = await self._pool_b.acquire(site_domain=domain)
            page = await slot.context.new_page()
            page.set_default_timeout(PAGE_GOTO_TIMEOUT)

            html, title = await self._render_page(
                page,
                url,
                selector="article, main, .content, .app, #app",
                wait_ms=PAGE_WAIT_RENDER_MS * 2,
                scroll_delay=1.0,
            )

            # 失败判定
            if self._is_pipeline_failure(html):
                return PipelineResult(
                    url=url, final_url=page.url, html=html, title=title,
                    method="pipeline3:pool_b",
                    success=False,
                    error="Pipeline 3: still blocked by WAF",
                )

            extracted = ContentExtractor(strategy=extract_strategy).extract(html, url)

            if len(extracted.content) < MIN_CONTENT_LENGTH:
                return PipelineResult(
                    url=url, final_url=page.url, html=html, title=title,
                    method="pipeline3:pool_b",
                    success=False,
                    error=f"Pipeline 3: content too short ({len(extracted.content)} chars)",
                )

            return PipelineResult(
                url=url, final_url=page.url,
                title=extracted.title or title, content=extracted.content, html=html,
                author=extracted.author, date=extracted.date,
                length=len(extracted.content), content_type="page",
                method="pipeline3:pool_b", success=True,
            )

        except Exception as e:
            return PipelineResult(
                url=url, success=False,
                error=f"Pipeline 3 exception: {str(e)[:200]}",
                method="pipeline3:error",
            )
        finally:
            if page:
                try:
                    await page.close()
                except Exception:
                    pass
            if slot:
                await self._pool_b.release(slot)

    # ============================================================
    # 管线 4: 付费墙专项（池 C）
    # ============================================================

    async def _pipeline_4_paywall(self, url: str, extract_strategy: str, **opts) -> PipelineResult:
        slot: Optional[BrowserSlot] = None
        page = None

        try:
            slot = await self._pool_c.acquire()
            page = await slot.context.new_page()
            page.set_default_timeout(PAGE_GOTO_TIMEOUT)

            html, title = await self._render_page(
                page,
                url,
                selector="article, main, .content",
                wait_ms=PAGE_WAIT_RENDER_MS * 2,
                scroll_delay=1.0,
            )

            extracted = ContentExtractor(strategy=extract_strategy).extract(html, url)

            success = len(extracted.content) >= MIN_CONTENT_LENGTH

            return PipelineResult(
                url=url, final_url=page.url,
                title=extracted.title or title, content=extracted.content, html=html,
                author=extracted.author, date=extracted.date,
                length=len(extracted.content), content_type="article",
                method="pipeline4:pool_c_bpc",
                success=success,
                error=None if success else "Pipeline 4: insufficient content after BPC",
                meta={"paywall": True},
            )

        except Exception as e:
            return PipelineResult(
                url=url, success=False,
                error=f"Pipeline 4 exception: {str(e)[:200]}",
                method="pipeline4:error",
            )
        finally:
            if page:
                try:
                    await page.close()
                except Exception:
                    pass
            if slot:
                await self._pool_c.release_and_destroy(slot)

    # ============================================================
    # 管线 5: 反封锁突破（Archive/Cache/Reader Mode）
    # ============================================================

    async def _pipeline_5_bypass(
        self,
        url: str,
        extract_strategy: str,
        previous_results: list,
        **opts,
    ) -> PipelineResult:
        """尝试多种反封锁突破策略。

        当管线 1-4 全部失败时，尝试：
        - Wayback Machine (archive.org)
        - Google Cache
        - archive.today (archive.ph)
        - Reader Mode URL
        - 社交媒体 Referer 伪装
        - 打印版/AMP 版 URL
        """
        # 收集之前管线的 HTML 用于墙类型检测
        original_html = ""
        original_content = ""
        for r in previous_results:
            if r.html:
                original_html = r.html
                original_content = r.content or ""
                break

        wall_type = WallDetector.detect_wall_type(original_html, original_content)
        logger.info("Pipeline 5 bypass: wall_type=%s for %s", wall_type, url)

        # 尝试各种突破方式
        bypass_attempts = []

        # 1. Wayback Machine
        bypass_attempts.append(("archive_org", self._try_archive_org(url)))
        # 2. Google Cache
        bypass_attempts.append(("google_cache", self._try_google_cache(url)))
        # 3. archive.today
        bypass_attempts.append(("archive_today", self._try_archive_today(url)))
        # 4. Reader Mode URL
        bypass_attempts.append(("reader_mode", self._try_reader_mode(url)))
        # 5. 社交媒体 Referer
        bypass_attempts.append(("referer_social", self._try_referer_social(url)))
        # 6. 打印版 URL
        bypass_attempts.append(("print_version", self._try_print_version(url)))

        for method_name, attempt in bypass_attempts:
            try:
                result = await attempt
                if result and result.success:
                    extracted = ContentExtractor(strategy=extract_strategy).extract(
                        result.html, url
                    )
                    if len(extracted.content) >= MIN_CONTENT_LENGTH:
                        return PipelineResult(
                            url=url,
                            final_url=result.final_url or url,
                            title=extracted.title,
                            content=extracted.content,
                            html=result.html,
                            author=extracted.author,
                            date=extracted.date,
                            length=len(extracted.content),
                            content_type="article",
                            method=f"pipeline5:{method_name}",
                            success=True,
                            meta={"bypass_method": method_name, "wall_type": wall_type},
                        )
            except Exception as e:
                logger.debug("Pipeline 5 %s failed: %s", method_name, e)

        return PipelineResult(
            url=url,
            success=False,
            error="Pipeline 5: all bypass methods failed",
            method="pipeline5:all_failed",
        )

    async def _try_archive_org(self, url: str) -> PipelineResult:
        """尝试 Wayback Machine"""
        import httpx
        archive_url = f"https://web.archive.org/web/2024/{url}"
        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
                resp = await client.get(archive_url)
                if resp.status_code == 200 and len(resp.text) > 1000:
                    return PipelineResult(url=url, html=resp.text, success=True, final_url=str(resp.url))
        except Exception:
            pass
        return PipelineResult(url=url, success=False)

    async def _try_google_cache(self, url: str) -> PipelineResult:
        """尝试 Google Cache"""
        import httpx
        cache_url = f"https://webcache.googleusercontent.com/search?q=cache:{url}"
        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
                resp = await client.get(cache_url)
                if resp.status_code == 200 and len(resp.text) > 1000:
                    return PipelineResult(url=url, html=resp.text, success=True, final_url=str(resp.url))
        except Exception:
            pass
        return PipelineResult(url=url, success=False)

    async def _try_archive_today(self, url: str) -> PipelineResult:
        """尝试 archive.today"""
        import httpx
        archive_url = f"https://archive.ph/newest/{url}"
        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
                resp = await client.get(archive_url)
                if resp.status_code == 200 and len(resp.text) > 1000:
                    return PipelineResult(url=url, html=resp.text, success=True, final_url=str(resp.url))
        except Exception:
            pass
        return PipelineResult(url=url, success=False)

    async def _try_reader_mode(self, url: str) -> PipelineResult:
        """尝试 Reader Mode URL（某些浏览器支持）"""
        import httpx
        # 尝试添加 ?reader=1 或 /amp 后缀
        for suffix in ["/amp", "?reader=1", "?output=amp"]:
            try:
                reader_url = url.rstrip("/") + suffix
                async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
                    resp = await client.get(reader_url)
                    if resp.status_code == 200 and len(resp.text) > 1000:
                        return PipelineResult(url=url, html=resp.text, success=True, final_url=str(resp.url))
            except Exception:
                continue
        return PipelineResult(url=url, success=False)

    async def _try_referer_social(self, url: str) -> PipelineResult:
        """尝试社交媒体 Referer 伪装"""
        import httpx
        referers = [
            "https://www.facebook.com/",
            "https://t.co/",
            "https://www.google.com/",
        ]
        for referer in referers:
            try:
                async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
                    resp = await client.get(
                        url,
                        headers={"Referer": referer},
                    )
                    if resp.status_code == 200 and len(resp.text) > 1000:
                        return PipelineResult(url=url, html=resp.text, success=True, final_url=str(resp.url))
            except Exception:
                continue
        return PipelineResult(url=url, success=False)

    async def _try_print_version(self, url: str) -> PipelineResult:
        """尝试打印版 URL"""
        import httpx
        # 常见的打印版 URL 模式
        patterns = [
            url.rstrip("/") + "?print=true",
            url.rstrip("/") + "?view=print",
            url.replace("/articles/", "/print/"),
        ]
        for print_url in patterns:
            try:
                async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
                    resp = await client.get(print_url)
                    if resp.status_code == 200 and len(resp.text) > 1000:
                        return PipelineResult(url=url, html=resp.text, success=True, final_url=str(resp.url))
            except Exception:
                continue
        return PipelineResult(url=url, success=False)

    # ============================================================
    # 辅助方法
    # ============================================================

    async def _render_page(
        self,
        page,
        url: str,
        *,
        selector: str,
        wait_ms: int,
        scroll_delay: float,
    ) -> tuple[str, str]:
        """渲染页面，支持懒加载滚动检测"""
        await page.goto(url, wait_until="domcontentloaded", timeout=PAGE_GOTO_TIMEOUT)
        try:
            await page.wait_for_selector(selector, timeout=wait_ms)
        except Exception:
            pass

        # 懒加载优化：滚动直到高度不再变化
        prev_height = 0
        max_scrolls = 10
        for _ in range(max_scrolls):
            current_height = await page.evaluate("document.body.scrollHeight")
            if current_height == prev_height:
                break  # 高度不再变化，停止滚动
            prev_height = current_height
            await page.evaluate("window.scrollBy(0, window.innerHeight)")
            await asyncio.sleep(scroll_delay)

        return await page.content(), await page.title()

    def _is_pipeline_failure(self, html: str) -> bool:
        """判断 HTML 是否触发管线失败条件"""
        html_lower = html.lower()
        for signal in PIPELINE_FAILURE_SIGNALS:
            if signal in html_lower:
                return True
        return False

    def _detect_paywall(self, result: PipelineResult) -> bool:
        """检测页面是否存在付费墙"""
        if not result.html:
            return False
        html_lower = result.html.lower()
        for signal in PAYWALL_DETECT_SIGNALS:
            if signal in html_lower:
                return True
        return False

    # ============================================================
    # 失败站点管理
    # ============================================================

    def get_failed_sites(self) -> dict[str, FailedSite]:
        """获取所有失败站点记录"""
        return dict(self._failed_sites)

    def clear_failed_site(self, domain: str):
        """手动清除某站点的失败标记（人工评估后重试）"""
        if domain in self._failed_sites:
            del self._failed_sites[domain]
            logger.info("Cleared failed site mark for %s", domain)

    def clear_all_failed_sites(self):
        """清除所有失败标记"""
        count = len(self._failed_sites)
        self._failed_sites.clear()
        logger.info("Cleared all %d failed site marks", count)

    def _cleanup_expired_failed(self):
        """清理过期的失败站点记录"""
        expired_domains = [
            domain for domain, failed in self._failed_sites.items()
            if failed.is_expired
        ]
        for domain in expired_domains:
            del self._failed_sites[domain]
            logger.info("Expired failed site mark for %s (auto-retry enabled)", domain)

    @property
    def stats(self) -> dict:
        return {
            "started": self._started,
            "pool_a": self._pool_a.stats if self._pool_a else {},
            "pool_b": self._pool_b.stats if self._pool_b else {},
            "pool_c": self._pool_c.stats if self._pool_c else {},
            "proxy_g1": self._proxy_g1.available_count,
            "proxy_g2": self._proxy_g2.available_count,
            "proxy_g3a": self._proxy_g3a.available_count,
            "proxy_g3b": self._proxy_g3b.available_count,
            "failed_sites": len(self._failed_sites),
            "pipeline_stats": self._pipeline_stats,
        }
