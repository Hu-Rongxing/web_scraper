# -*- coding: utf-8 -*-
"""Article content extraction.

Production article extraction is intentionally limited to trafilatura. Scrapling
is used by the fetch/render layers and by LinkExtractor for DOM link discovery;
it is not a second article text engine.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from .config import DEFAULT_EXTRACT_STRATEGY, MIN_CONTENT_LENGTH, logger

try:
    import trafilatura
except ImportError:  # pragma: no cover - depends on local environment
    trafilatura = None


@dataclass
class ExtractedContent:
    """Normalized article extraction result."""

    title: str = ""
    content: str = ""
    author: Optional[str] = None
    date: Optional[str] = None
    summary: Optional[str] = None
    raw_html: str = ""
    method: str = ""


class ContentExtractor:
    """Extract readable article text with trafilatura only."""

    SUPPORTED_STRATEGY = "trafilatura"

    def __init__(self, strategy: Optional[str] = None):
        self._strategy = strategy or DEFAULT_EXTRACT_STRATEGY

    def extract(self, html: str, url: str = "", **_: object) -> ExtractedContent:
        """Extract article content from already fetched HTML."""
        if self._strategy != self.SUPPORTED_STRATEGY:
            logger.warning(
                "Unsupported extract strategy %r; using trafilatura",
                self._strategy,
            )
        return self._extract_trafilatura(html, url)

    def _extract_trafilatura(self, html: str, url: str) -> ExtractedContent:
        if not html:
            return ExtractedContent(method="trafilatura_empty")

        if trafilatura is None:
            logger.error("trafilatura is not installed; article extraction disabled")
            return ExtractedContent(
                title=self._extract_title_from_html(html),
                raw_html=html,
                method="trafilatura_unavailable",
            )

        try:
            content = trafilatura.extract(
                html,
                url=url,
                include_links=False,
                include_images=False,
                include_formatting=False,
                include_comments=False,
                deduplicate=True,
            )
            metadata = trafilatura.extract_metadata(html, default_url=url)
        except Exception as exc:
            logger.warning("trafilatura extraction failed: %s", exc)
            return ExtractedContent(
                title=self._extract_title_from_html(html),
                raw_html=html,
                method="trafilatura_error",
            )

        title = ""
        author = None
        date = None
        if metadata:
            title = metadata.title or ""
            author = metadata.author
            date = metadata.date
        if not title:
            title = self._extract_title_from_html(html)

        if not content or len(content.strip()) < MIN_CONTENT_LENGTH:
            return ExtractedContent(
                title=self._clean_title(title),
                author=author,
                date=date,
                raw_html=html,
                method="trafilatura_short",
            )

        return ExtractedContent(
            title=self._clean_title(title),
            content=content.strip(),
            author=author,
            date=date,
            raw_html=html,
            method="trafilatura",
        )

    @staticmethod
    def _clean_title(title: str) -> str:
        if not title:
            return ""
        title = re.sub(r"<[^>]+>", "", title)
        title = re.sub(r"&(?:amp|lt|gt|quot|nbsp|#\d+|#x[0-9a-fA-F]+);", " ", title)
        title = re.sub(r"\s+", " ", title).strip()
        title = re.sub(r"\s*[-|]\s*(?:Home|News|The .*|.*\.com|.*\.org)\s*$", "", title, flags=re.I)
        return title

    @staticmethod
    def _extract_title_from_html(html: str) -> str:
        for pattern in (
            r"<title[^>]*>(.+?)</title>",
            r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\'](.+?)["\']',
            r"<h1[^>]*>(.+?)</h1>",
        ):
            match = re.search(pattern, html, re.I | re.S)
            if not match:
                continue
            raw = re.sub(r"<[^>]+>", "", match.group(1))
            raw = re.sub(r"\s+", " ", raw).strip()
            if raw and len(raw) < 300:
                return raw
        return ""
