# -*- coding: utf-8 -*-
"""Pipeline manager for web_scraper.

The manager keeps the public five-stage degradation model while making the
lightweight access paths broad and diagnosable:

1. HTTP clients with browser-like fingerprints.
2. Basic browser render.
3. High-protection browser render.
4. Paywall/BPC browser render.
5. Reader/archive/AMP/print/referer fallbacks.
"""

from __future__ import annotations

import asyncio
import gzip
import importlib.util
import re
import time
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import quote_plus, urlparse

from ..browser_pool import BrowserSlot, PoolA, PoolB, PoolC
from ..config import (
    MIN_CONTENT_LENGTH,
    PAGE_GOTO_TIMEOUT,
    PAGE_WAIT_RENDER_MS,
    PAYWALL_DETECT_SIGNALS,
    PIPELINE_FAILURE_SIGNALS,
    PROXY_GROUP_1,
    PROXY_GROUP_2,
    PROXY_GROUP_3A,
    PROXY_GROUP_3B,
    USER_AGENT,
    logger,
)
from ..content_extractor import ContentExtractor
from ..models import PipelineResult
from ..proxies import PipelineProxyPool, ResidentialRotatingPool, StaticBoundPool
from .anti_block import WallDetector
from .levels import PipelineLevel


class PipelineError(Exception):
    """Pipeline execution error with the failed level attached."""

    def __init__(self, message: str, pipeline_level: int, cause: Optional[Exception] = None):
        super().__init__(message)
        self.pipeline_level = pipeline_level
        self.cause = cause


@dataclass
class FailedSite:
    """Temporary record for a domain that failed all access paths."""

    domain: str
    url: str
    failed_at: float
    reason: str
    pipeline_results: list[PipelineResult] = field(default_factory=list)
    expires_at: float = 0.0

    def __post_init__(self) -> None:
        if self.expires_at == 0.0:
            self.expires_at = self.failed_at + 86400

    @property
    def is_expired(self) -> bool:
        return time.time() > self.expires_at


class PipelineManager:
    """Five-level fetch pipeline with lazy browser pools and rich diagnostics."""

    def __init__(self):
        self._proxy_g1 = PipelineProxyPool(PROXY_GROUP_1)
        self._proxy_g2 = ResidentialRotatingPool(PROXY_GROUP_2)
        self._proxy_g3a = StaticBoundPool(PROXY_GROUP_3A, pool_name="pool_b")
        self._proxy_g3b = StaticBoundPool(PROXY_GROUP_3B, pool_name="pool_c")

        self._pool_a: Optional[PoolA] = None
        self._pool_b: Optional[PoolB] = None
        self._pool_c: Optional[PoolC] = None
        self._started = False
        self._failed_sites: dict[str, FailedSite] = {}
        self._pipeline_stats: dict[object, dict[str, int] | int] = {
            1: {"success": 0, "failure": 0},
            2: {"success": 0, "failure": 0},
            3: {"success": 0, "failure": 0},
            4: {"success": 0, "failure": 0},
            5: {"success": 0, "failure": 0},
            "degradation_count": 0,
        }

    async def start(self) -> None:
        self._started = True
        logger.info("PipelineManager started: lazy browser pools, 5-level degradation")

    async def shutdown(self) -> None:
        await asyncio.gather(
            self._pool_a.shutdown() if self._pool_a else asyncio.sleep(0),
            self._pool_b.shutdown() if self._pool_b else asyncio.sleep(0),
            self._pool_c.shutdown() if self._pool_c else asyncio.sleep(0),
        )
        self._pool_a = None
        self._pool_b = None
        self._pool_c = None
        self._started = False
        logger.info("PipelineManager shutdown")

    async def fetch(
        self,
        url: str,
        extract_strategy: str = "trafilatura",
        **opts,
    ) -> PipelineResult:
        if not self._started:
            await self.start()

        self._cleanup_expired_failed()
        domain = urlparse(url).netloc
        failed = self._failed_sites.get(domain)
        if failed:
            return PipelineResult(
                url=url,
                success=False,
                error=f"Site temporarily unscrapable: {failed.reason}",
                method="blocked:failed_site",
                meta={"failed_site": True, "domain": domain},
            )

        requested_level = opts.get("pipeline_level")
        levels = self._levels_from(requested_level, skip_browser=bool(opts.get("skip_browser")))
        level_timeout = float(opts.get("level_timeout_sec", 15.0))
        t0 = time.monotonic()
        results: list[PipelineResult] = []

        previous_results: list[PipelineResult] = []

        for level in levels:
            timeout = self._timeout_for_level(level, level_timeout, opts)
            try:
                result = await asyncio.wait_for(
                    self._run_level(level, url, extract_strategy, previous_results=previous_results, **opts),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                result = PipelineResult(
                    url=url,
                    success=False,
                    method=f"pipeline{level}:timeout",
                    error=f"Pipeline {level} timeout after {timeout:.1f}s",
                )
            result.pipeline_level = level if result.success else result.pipeline_level
            results.append(result)
            if result.success and (level != PipelineLevel.HIGH_PROTECT or not self._detect_paywall(result)):
                result.elapsed_ms = (time.monotonic() - t0) * 1000
                self._mark_stats(level, True, degraded=len(results) > 1)
                return result
            self._mark_stats(level, False, degraded=len(results) > 1)
            previous_results.append(result)

        elapsed = (time.monotonic() - t0) * 1000
        error_summary = "; ".join(r.error or r.method or "unknown" for r in results)
        self._failed_sites[domain] = FailedSite(
            domain=domain,
            url=url,
            failed_at=time.time(),
            reason=error_summary[:500],
            pipeline_results=results,
        )
        return PipelineResult(
            url=url,
            success=False,
            error=f"All 5 pipelines failed: {error_summary[:300]}",
            elapsed_ms=elapsed,
            method="pipeline:all_failed",
            meta={
                "all_pipelines_failed": True,
                "domain": domain,
                "attempts": [self._result_meta(r) for r in results],
            },
        )

    def _levels_from(self, requested_level: object, *, skip_browser: bool = False) -> list[int]:
        if requested_level in {PipelineLevel.HTTP, PipelineLevel.BASIC_RENDER, PipelineLevel.HIGH_PROTECT, PipelineLevel.PAYWALL, 5}:
            start = int(requested_level)
            levels = [level for level in [1, 2, 3, 4, 5] if level >= start]
        else:
            levels = [1, 2, 3, 4, 5]
        if skip_browser:
            levels = [level for level in levels if level in {PipelineLevel.HTTP, 5}]
        return levels

    async def _run_level(
        self,
        level: int,
        url: str,
        extract_strategy: str,
        *,
        previous_results: list[PipelineResult],
        **opts,
    ) -> PipelineResult:
        if level == PipelineLevel.HTTP:
            return await self._pipeline_1_http(url, extract_strategy, **opts)
        if level == PipelineLevel.BASIC_RENDER:
            return await self._pipeline_2_basic_render(url, extract_strategy, **opts)
        if level == PipelineLevel.HIGH_PROTECT:
            return await self._pipeline_3_high_protection(url, extract_strategy, **opts)
        if level == PipelineLevel.PAYWALL:
            return await self._pipeline_4_paywall(url, extract_strategy, **opts)
        return await self._pipeline_5_bypass(url, extract_strategy, previous_results, **opts)

    def _timeout_for_level(self, level: int, base_timeout: float, opts: dict) -> float:
        if level == PipelineLevel.HTTP:
            return float(opts.get("http_timeout_sec", min(base_timeout, 20.0)))
        if level in {PipelineLevel.BASIC_RENDER, PipelineLevel.HIGH_PROTECT}:
            return float(opts.get("browser_timeout_sec", min(base_timeout, 12.0)))
        if level == PipelineLevel.PAYWALL:
            return float(opts.get("paywall_timeout_sec", min(base_timeout, 15.0)))
        return float(opts.get("bypass_timeout_sec", max(base_timeout, 20.0)))

    async def _pipeline_1_http(self, url: str, extract_strategy: str, **opts) -> PipelineResult:
        proxy = await self._proxy_g1.acquire()
        proxy_success = False
        t0 = time.monotonic()
        errors: list[str] = []

        try:
            for fetch_method in (
                self._try_curl_cffi_http,
                self._try_scrapling_http,
                self._try_httpx_http,
            ):
                try:
                    html, final_url, method = await fetch_method(url, proxy=proxy, timeout=opts.get("timeout", 30))
                except Exception as exc:
                    errors.append(f"{fetch_method.__name__}: {str(exc)[:160]}")
                    continue

                if self._is_pipeline_failure(html):
                    errors.append(f"{method}: blocked/challenge markers")
                    continue

                result = self._extract_result(
                    url=url,
                    final_url=final_url,
                    html=html,
                    method=f"pipeline1:{method}",
                    extract_strategy=extract_strategy,
                    elapsed_ms=(time.monotonic() - t0) * 1000,
                )
                if result.success:
                    proxy_success = True
                    return result
                errors.append(f"{method}: {result.error}")

            return PipelineResult(
                url=url,
                success=False,
                method="pipeline1:http_all_failed",
                error="Pipeline 1 HTTP attempts failed: " + "; ".join(errors),
                elapsed_ms=(time.monotonic() - t0) * 1000,
                meta={"http_errors": errors},
            )
        finally:
            if proxy:
                await self._proxy_g1.release(proxy, success=proxy_success)

    async def _try_curl_cffi_http(self, url: str, *, proxy: Optional[str], timeout: float) -> tuple[str, str, str]:
        try:
            from curl_cffi import requests as curl_requests
        except ImportError as exc:
            raise RuntimeError("curl_cffi unavailable") from exc

        proxies = {"http": proxy, "https": proxy} if proxy else None
        errors: list[str] = []
        for target in ("chrome124", "chrome", "chrome_android", "safari"):
            try:
                resp = await asyncio.to_thread(
                    curl_requests.get,
                    url,
                    headers=self._desktop_headers(url),
                    proxies=proxies,
                    timeout=timeout,
                    allow_redirects=True,
                    impersonate=target,
                )
            except Exception as exc:
                errors.append(f"{target}: {str(exc)[:80]}")
                continue
            if resp.status_code >= 400:
                errors.append(f"{target}: HTTP {resp.status_code}")
                continue
            return resp.text, str(resp.url), f"curl_cffi_{target}"
        raise RuntimeError("; ".join(errors) or "curl_cffi attempts failed")

    async def _try_scrapling_http(self, url: str, *, proxy: Optional[str], timeout: float) -> tuple[str, str, str]:
        try:
            from scrapling import Fetcher
        except ImportError as exc:
            raise RuntimeError("scrapling unavailable") from exc

        fetcher = Fetcher(auto_referer=True, timeout=timeout)
        resp = await asyncio.to_thread(fetcher.get, url, proxy=proxy)
        html = resp.html_content if hasattr(resp, "html_content") else resp.content if hasattr(resp, "content") else resp.html
        if isinstance(html, bytes):
            html = self._decode_bytes(html)
        return str(html or ""), str(resp.url), "scrapling_fetcher"

    async def _try_httpx_http(self, url: str, *, proxy: Optional[str], timeout: float) -> tuple[str, str, str]:
        import httpx

        kwargs = {
            "follow_redirects": True,
            "headers": self._desktop_headers(url),
            "timeout": timeout,
            "http2": self._http2_available(),
        }
        if proxy:
            kwargs["proxy"] = proxy
        async with httpx.AsyncClient(**kwargs) as client:
            resp = await client.get(url)
            if resp.status_code >= 400:
                raise RuntimeError(f"HTTP {resp.status_code}")
            return resp.text, str(resp.url), "httpx_http2"

    async def _pipeline_2_basic_render(self, url: str, extract_strategy: str, **opts) -> PipelineResult:
        await self._ensure_pool_a()
        return await self._browser_fetch(url, extract_strategy, pool="a", method="pipeline2:pool_a")

    async def _pipeline_3_high_protection(self, url: str, extract_strategy: str, **opts) -> PipelineResult:
        await self._ensure_pool_b()
        return await self._browser_fetch(url, extract_strategy, pool="b", method="pipeline3:pool_b")

    async def _pipeline_4_paywall(self, url: str, extract_strategy: str, **opts) -> PipelineResult:
        await self._ensure_pool_c()
        return await self._browser_fetch(url, extract_strategy, pool="c", method="pipeline4:pool_c_bpc")

    async def _ensure_pool_a(self) -> None:
        if not self._pool_a:
            self._pool_a = PoolA(proxy_provider=self._proxy_g2)
            await self._pool_a.start()

    async def _ensure_pool_b(self) -> None:
        if not self._pool_b:
            self._pool_b = PoolB(proxy_provider=self._proxy_g3a)
            await self._pool_b.start()

    async def _ensure_pool_c(self) -> None:
        if not self._pool_c:
            self._pool_c = PoolC(proxy_provider=self._proxy_g3b)
            await self._pool_c.start()

    async def _browser_fetch(self, url: str, extract_strategy: str, *, pool: str, method: str) -> PipelineResult:
        slot: Optional[BrowserSlot] = None
        page = None
        t0 = time.monotonic()
        try:
            if pool == "a":
                slot = await self._pool_a.acquire()  # type: ignore[union-attr]
            elif pool == "b":
                slot = await self._pool_b.acquire(site_domain=urlparse(url).netloc)  # type: ignore[union-attr]
            else:
                slot = await self._pool_c.acquire()  # type: ignore[union-attr]
            page = await slot.context.new_page()
            page.set_default_timeout(PAGE_GOTO_TIMEOUT)
            await page.goto(url, wait_until="domcontentloaded", timeout=PAGE_GOTO_TIMEOUT)
            try:
                await page.wait_for_selector("article, main, .content, .app, #app, body", timeout=PAGE_WAIT_RENDER_MS)
            except Exception:
                pass
            await self._humanish_scroll(page)
            html = await page.content()
            if self._is_pipeline_failure(html):
                return PipelineResult(
                    url=url,
                    final_url=page.url,
                    html=html,
                    method=method,
                    success=False,
                    error=f"{method}: blocked/challenge markers",
                    elapsed_ms=(time.monotonic() - t0) * 1000,
                )
            return self._extract_result(
                url=url,
                final_url=page.url,
                html=html,
                method=method,
                extract_strategy=extract_strategy,
                elapsed_ms=(time.monotonic() - t0) * 1000,
                meta={"browser_pool": pool},
            )
        except Exception as exc:
            return PipelineResult(
                url=url,
                success=False,
                method=f"{method}:error",
                error=f"{method} exception: {str(exc)[:220]}",
                elapsed_ms=(time.monotonic() - t0) * 1000,
            )
        finally:
            if page:
                try:
                    await page.close()
                except Exception:
                    pass
            if slot:
                if pool == "a":
                    await self._pool_a.release(slot)  # type: ignore[union-attr]
                elif pool == "b":
                    await self._pool_b.release(slot)  # type: ignore[union-attr]
                else:
                    await self._pool_c.release_and_destroy(slot)  # type: ignore[union-attr]

    async def _pipeline_5_bypass(
        self,
        url: str,
        extract_strategy: str,
        previous_results: list[PipelineResult],
        **opts,
    ) -> PipelineResult:
        original_html = next((r.html for r in previous_results if r.html), "")
        original_content = next((r.content for r in previous_results if r.content), "")
        wall_type = WallDetector.detect_wall_type(original_html, original_content)
        method_timeout = float(opts.get("bypass_method_timeout_sec", 5.0))
        t0 = time.monotonic()
        errors: dict[str, str] = {}

        attempts = (
            ("jina_reader", self._try_jina_reader),
            ("amp_print_reader", self._try_amp_print_reader),
            ("referer_variants", self._try_referer_variants),
            ("archive_org", self._try_archive_org),
            ("archive_today", self._try_archive_today),
            ("google_cache", self._try_google_cache),
        )
        for name, fn in attempts:
            try:
                result = await asyncio.wait_for(fn(url, timeout=method_timeout), timeout=method_timeout + 1.0)
            except asyncio.TimeoutError:
                errors[name] = f"timeout after {method_timeout:.1f}s"
                continue
            if result.success:
                extracted = ContentExtractor(strategy=extract_strategy).extract(result.html, url)
                quality_error = self._p5_quality_error(url, result.final_url, name, extracted)
                if not quality_error:
                    result.title = extracted.title
                    result.content = extracted.content
                    result.author = extracted.author
                    result.date = extracted.date
                    result.length = len(extracted.content)
                    result.content_type = "article"
                    result.method = f"pipeline5:{name}"
                    result.pipeline_level = 5
                    result.elapsed_ms = (time.monotonic() - t0) * 1000
                    result.meta.update({"bypass_method": name, "wall_type": wall_type})
                    return result
                errors[name] = quality_error
            else:
                errors[name] = result.error or "no usable body"

        return PipelineResult(
            url=url,
            success=False,
            method="pipeline5:all_failed",
            error="Pipeline 5: all bypass methods failed",
            elapsed_ms=(time.monotonic() - t0) * 1000,
            meta={"bypass_errors": errors, "wall_type": wall_type},
        )

    async def _try_jina_reader(self, url: str, *, timeout: float = 5.0) -> PipelineResult:
        import httpx

        variants = self._jina_reader_urls(url)
        headers = self._desktop_headers(url, accept="text/plain, text/markdown, */*")
        errors: list[str] = []
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=timeout,
            headers=headers,
            http2=self._http2_available(),
        ) as client:
            for reader_url in variants:
                try:
                    resp = await client.get(reader_url)
                    text = resp.text or ""
                    if resp.status_code != 200:
                        errors.append(f"{reader_url}: HTTP {resp.status_code}")
                        continue
                    if len(text) < MIN_CONTENT_LENGTH:
                        errors.append(f"{reader_url}: too short")
                        continue
                    if self._is_reader_failure(text):
                        errors.append(f"{reader_url}: reader failure shell")
                        continue
                    return PipelineResult(url=url, final_url=str(resp.url), html=text, success=True, method="pipeline5:jina_reader")
                except Exception as exc:
                    errors.append(f"{reader_url}: {str(exc)[:120]}")
        return PipelineResult(url=url, success=False, method="pipeline5:jina_reader", error="; ".join(errors[:6]))

    def _jina_reader_urls(self, url: str) -> list[str]:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return []
        query = f"?{parsed.query}" if parsed.query else ""
        netloc_path = f"{parsed.netloc}{parsed.path}{query}"
        urls = [
            f"https://r.jina.ai/http://{url}",
            f"https://r.jina.ai/http://{parsed.scheme}://{netloc_path}",
            f"https://r.jina.ai/http://http://{netloc_path}",
            f"https://r.jina.ai/http://https://{netloc_path}",
        ]
        if parsed.netloc.startswith("www."):
            bare = parsed.netloc[4:]
            urls.extend([
                f"https://r.jina.ai/http://https://{bare}{parsed.path}{query}",
                f"https://r.jina.ai/http://http://{bare}{parsed.path}{query}",
            ])
        else:
            urls.extend([
                f"https://r.jina.ai/http://https://www.{parsed.netloc}{parsed.path}{query}",
                f"https://r.jina.ai/http://http://www.{parsed.netloc}{parsed.path}{query}",
            ])
        return list(dict.fromkeys(urls))

    async def _try_amp_print_reader(self, url: str, *, timeout: float = 5.0) -> PipelineResult:
        candidates = self._variant_urls(url)
        errors: list[str] = []
        for candidate in candidates:
            result = await self._try_http_variant(candidate, method="pipeline5:variant", timeout=timeout)
            if result.success:
                return result
            errors.append(result.error or candidate)
        return PipelineResult(url=url, success=False, method="pipeline5:variant", error="; ".join(errors[:5]))

    def _variant_urls(self, url: str) -> list[str]:
        parsed = urlparse(url)
        sep = "&" if parsed.query else "?"
        variants = [
            f"{url.rstrip('/')}/amp",
            f"{url}{sep}amp=1",
            f"{url}{sep}output=amp",
            f"{url}{sep}view=print",
            f"{url}{sep}print=1",
            url.replace("/articles/", "/amp/articles/"),
            url.replace("/article/", "/print/"),
        ]
        return list(dict.fromkeys(variants))

    async def _try_referer_variants(self, url: str, *, timeout: float = 5.0) -> PipelineResult:
        referers = [
            "https://www.google.com/",
            "https://news.google.com/",
            "https://www.facebook.com/",
            "https://t.co/",
            "https://www.reddit.com/",
            "https://news.ycombinator.com/",
        ]
        errors: list[str] = []
        for referer in referers:
            result = await self._try_http_variant(url, method="pipeline5:referer", headers={"Referer": referer}, timeout=timeout)
            if result.success:
                result.meta["referer"] = referer
                return result
            errors.append(result.error or referer)
        return PipelineResult(url=url, success=False, method="pipeline5:referer", error="; ".join(errors[:5]))

    async def _try_archive_org(self, url: str, *, timeout: float = 5.0) -> PipelineResult:
        urls = [
            f"https://web.archive.org/web/20240000000000*/{url}",
            f"https://webcache.googleusercontent.com/search?q={quote_plus(url)}",
        ]
        for candidate in urls:
            result = await self._try_http_variant(candidate, method="pipeline5:archive_org", timeout=timeout)
            if result.success:
                return result
        return PipelineResult(url=url, success=False, method="pipeline5:archive_org", error="No usable archive.org result")

    async def _try_archive_today(self, url: str, *, timeout: float = 5.0) -> PipelineResult:
        return await self._try_http_variant(f"https://archive.ph/newest/{url}", method="pipeline5:archive_today", timeout=timeout)

    async def _try_google_cache(self, url: str, *, timeout: float = 5.0) -> PipelineResult:
        return await self._try_http_variant(f"https://webcache.googleusercontent.com/search?q=cache:{url}", method="pipeline5:google_cache", timeout=timeout)

    async def _try_http_variant(
        self,
        url: str,
        *,
        method: str,
        headers: Optional[dict[str, str]] = None,
        timeout: float = 5.0,
    ) -> PipelineResult:
        import httpx

        request_headers = self._desktop_headers(url)
        if headers:
            request_headers.update(headers)
        try:
            async with httpx.AsyncClient(
                follow_redirects=True,
                timeout=timeout,
                headers=request_headers,
                http2=self._http2_available(),
            ) as client:
                resp = await client.get(url)
                text = resp.text or ""
                if resp.status_code >= 400:
                    return PipelineResult(url=url, final_url=str(resp.url), html=text, success=False, method=method, error=f"HTTP {resp.status_code}")
                if len(text) < MIN_CONTENT_LENGTH:
                    return PipelineResult(url=url, final_url=str(resp.url), html=text, success=False, method=method, error=f"too short ({len(text)} chars)")
                if self._is_pipeline_failure(text) or self._is_reader_failure(text):
                    return PipelineResult(url=url, final_url=str(resp.url), html=text, success=False, method=method, error="challenge/failure shell")
                return PipelineResult(url=url, final_url=str(resp.url), html=text, success=True, method=method)
        except Exception as exc:
            return PipelineResult(url=url, success=False, method=method, error=str(exc)[:220])

    def _extract_result(
        self,
        *,
        url: str,
        final_url: str,
        html: str,
        method: str,
        extract_strategy: str,
        elapsed_ms: float,
        meta: Optional[dict] = None,
    ) -> PipelineResult:
        extracted = ContentExtractor(strategy=extract_strategy).extract(html, url)
        if len(extracted.content) < MIN_CONTENT_LENGTH:
            return PipelineResult(
                url=url,
                final_url=final_url,
                html=html,
                title=extracted.title,
                method=method,
                success=False,
                error=f"{method}: content too short ({len(extracted.content)} chars)",
                elapsed_ms=elapsed_ms,
                meta=meta or {},
            )
        return PipelineResult(
            url=url,
            final_url=final_url,
            title=extracted.title,
            content=extracted.content,
            html=html,
            author=extracted.author,
            date=extracted.date,
            length=len(extracted.content),
            content_type="page",
            method=method,
            success=True,
            elapsed_ms=elapsed_ms,
            meta=meta or {},
        )

    async def _humanish_scroll(self, page) -> None:
        for _ in range(3):
            try:
                await page.evaluate("window.scrollBy(0, Math.max(250, window.innerHeight * 0.8))")
            except Exception:
                break
            await asyncio.sleep(0.25)

    def _is_pipeline_failure(self, html: str) -> bool:
        sample = (html or "")[:8000].lower()
        return any(signal.lower() in sample for signal in PIPELINE_FAILURE_SIGNALS)

    def _is_reader_failure(self, text: str) -> bool:
        sample = (text or "")[:3000].lower()
        markers = [
            "warning: target url returned error",
            "securitycompromiseerror",
            "anonymous access to domain",
            "title: wayback machine",
            "wayback machine",
            "calendar view",
            "saved from",
            "hubble-focused crawl",
            "webcache.googleusercontent.com",
            "title: just a moment",
            "checking your browser",
            "please enable js and disable any ad blocker",
            "please enable javascript and disable any ad blocker",
            "captcha",
            "access denied",
            "ddos attack suspected",
        ]
        return any(marker in sample for marker in markers) or bool(re.search(r'"code"\s*:\s*(401|403|451|429)', sample))

    def _p5_quality_error(
        self,
        original_url: str,
        final_url: str,
        bypass_method: str,
        extracted,
    ) -> str:
        content_length = len(extracted.content or "")
        if content_length < MIN_CONTENT_LENGTH:
            return f"content too short ({content_length} chars)"

        title = (extracted.title or "").strip().lower()
        content_sample = (extracted.content or "")[:3000].lower()
        if "wayback machine" in title or "wayback machine" in content_sample:
            return "archive/search shell"
        if "webcache.googleusercontent.com" in content_sample:
            return "cache shell"

        if bypass_method in {"archive_org", "archive_today", "google_cache"}:
            original_domain = self._registrable_domain(urlparse(original_url).netloc)
            text = f"{final_url}\n{extracted.title}\n{extracted.content[:3000]}".lower()
            if original_domain and original_domain not in text:
                return f"archive result not tied to source domain ({original_domain})"
            if content_length < max(MIN_CONTENT_LENGTH * 3, 600):
                return f"archive content too short ({content_length} chars)"

        return ""

    def _detect_paywall(self, result: PipelineResult) -> bool:
        sample = (result.html or "")[:12000].lower()
        return any(signal.lower() in sample for signal in PAYWALL_DETECT_SIGNALS)

    def _desktop_headers(self, url: str, *, accept: Optional[str] = None) -> dict[str, str]:
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}/" if parsed.scheme and parsed.netloc else "https://www.google.com/"
        return {
            "Accept": accept or "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Referer": origin,
            "Upgrade-Insecure-Requests": "1",
            "User-Agent": USER_AGENT,
        }

    @staticmethod
    def _registrable_domain(netloc: str) -> str:
        host = netloc.split("@")[-1].split(":")[0].lower()
        if host.startswith("www."):
            host = host[4:]
        return host

    @staticmethod
    def _decode_bytes(data: bytes, content_encoding: str = "") -> str:
        if content_encoding.lower() == "gzip":
            data = gzip.decompress(data)
        for encoding in ("utf-8", "gb18030", "big5", "latin-1"):
            try:
                return data.decode(encoding)
            except UnicodeDecodeError:
                continue
        return data.decode("utf-8", errors="replace")

    @staticmethod
    def _http2_available() -> bool:
        return importlib.util.find_spec("h2") is not None

    def _mark_stats(self, level: int, success: bool, *, degraded: bool) -> None:
        bucket = self._pipeline_stats.get(level)
        if isinstance(bucket, dict):
            bucket["success" if success else "failure"] += 1
        if degraded:
            self._pipeline_stats["degradation_count"] = int(self._pipeline_stats["degradation_count"]) + 1

    @staticmethod
    def _result_meta(result: PipelineResult) -> dict:
        return {
            "method": result.method,
            "success": result.success,
            "error": result.error,
            "final_url": result.final_url,
            "length": result.length,
            "pipeline_level": result.pipeline_level,
            "meta": result.meta,
        }

    def get_failed_sites(self) -> dict[str, FailedSite]:
        return dict(self._failed_sites)

    def clear_failed_site(self, domain: str) -> None:
        self._failed_sites.pop(domain, None)

    def clear_all_failed_sites(self) -> None:
        self._failed_sites.clear()

    def _cleanup_expired_failed(self) -> None:
        for domain in [domain for domain, failed in self._failed_sites.items() if failed.is_expired]:
            del self._failed_sites[domain]

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
