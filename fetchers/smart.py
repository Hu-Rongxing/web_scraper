# -*- coding: utf-8 -*-
"""SmartFetcher public entry point."""

from __future__ import annotations

import asyncio
from typing import Optional

from ..config import ExtractStrategy, logger
from ..link_extractor import ExtractedLink, LinkExtractor
from ..models import FetchResult, PipelineResult
from ..pipelines import PipelineManager


class SmartFetcher:
    """Unified fetcher with pipeline degradation and focused extractors."""

    def __init__(self, **kwargs):
        self._pipeline: Optional[PipelineManager] = None
        self._started = False

    async def start(self):
        if self._started:
            return
        self._pipeline = PipelineManager()
        await self._pipeline.start()
        self._started = True
        logger.info("SmartFetcher ready")

    async def shutdown(self):
        if not self._started:
            return
        if self._pipeline:
            await self._pipeline.shutdown()
        self._started = False
        logger.info("SmartFetcher shutdown")

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, *args):
        await self.shutdown()

    async def fetch(
        self,
        url: str,
        extract_strategy: str = ExtractStrategy.TRAFILATURA,
        **opts,
    ) -> FetchResult:
        """Fetch one URL and extract article content with trafilatura."""
        if not self._started:
            await self.start()

        result = await self._pipeline.fetch(
            url,
            extract_strategy=extract_strategy,
            **opts,
        )
        return self._convert_result(result)

    async def fetch_links(
        self,
        url: str,
        *,
        css: str = "a[href]",
        same_domain: bool = True,
        include_domains: list[str] | None = None,
        min_title_length: int = 1,
        max_title_length: int = 240,
        **opts,
    ) -> list[ExtractedLink]:
        """Fetch a list page and extract links with Scrapling DOM parsing."""
        if not self._started:
            await self.start()

        result = await self._pipeline.fetch(
            url,
            extract_strategy=ExtractStrategy.TRAFILATURA,
            **opts,
        )
        if not result.html:
            return []

        return LinkExtractor().extract(
            result.html,
            result.final_url or url,
            css=css,
            same_domain=same_domain,
            include_domains=include_domains,
            min_title_length=min_title_length,
            max_title_length=max_title_length,
        )

    async def fetch_many(
        self,
        urls: list[str],
        extract_strategy: str = ExtractStrategy.TRAFILATURA,
        **opts,
    ) -> list[FetchResult]:
        """Fetch multiple URLs using the same content strategy."""
        if not self._started:
            await self.start()
        tasks = [
            self.fetch(url, extract_strategy=extract_strategy, **opts)
            for url in urls
        ]
        return await asyncio.gather(*tasks)

    @staticmethod
    def _convert_result(pr: PipelineResult) -> FetchResult:
        return FetchResult(
            url=pr.url,
            final_url=pr.final_url,
            title=pr.title,
            content=pr.content,
            html=pr.html,
            author=pr.author,
            date=pr.date,
            summary=pr.summary,
            length=pr.length,
            content_type=pr.content_type,
            method=pr.method,
            success=pr.success,
            error=pr.error,
            elapsed_ms=pr.elapsed_ms,
            meta={**pr.meta, "pipeline_level": pr.pipeline_level},
        )

    def stats(self) -> dict:
        return {
            "started": self._started,
            "version": "3.1",
            "pipelines": self._pipeline.stats if self._pipeline else {},
        }
