# -*- coding: utf-8 -*-
"""Article content extraction.

Production article extraction uses trafilatura first and Scrapling DOM text as
the fallback. This keeps article extraction scoped to the two project-standard
engines and avoids readability-lxml as a separate extraction path.
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

try:
    from scrapling import Selector
except ImportError:  # pragma: no cover - depends on local environment
    Selector = None


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
    """Extract readable article text with trafilatura and Scrapling fallback."""

    SUPPORTED_STRATEGY = "trafilatura"
    FALLBACK_SELECTORS = (
        "article",
        '[data-testid="article-body"]',
        '[role="article"]',
        "main",
        "body",
    )

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
            logger.error("trafilatura is not installed; falling back to Scrapling")
            return self._extract_scrapling(html, method="scrapling_fallback_unavailable")

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
            return self._extract_scrapling(html, method="scrapling_fallback_error")

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
            fallback = self._extract_scrapling(
                html,
                method="scrapling_fallback_short",
                title=title,
                author=author,
                date=date,
            )
            if fallback.content:
                return fallback
            fallback.method = "trafilatura_short"
            return fallback

        return ExtractedContent(
            title=self._clean_title(title),
            content=content.strip(),
            author=author,
            date=date,
            raw_html=html,
            method="trafilatura",
        )

    def _extract_scrapling(
        self,
        html: str,
        *,
        method: str,
        title: str = "",
        author: Optional[str] = None,
        date: Optional[str] = None,
    ) -> ExtractedContent:
        """Fallback article extraction using Scrapling DOM text."""
        if not html:
            return ExtractedContent(method=method)

        if Selector is None:
            logger.error("scrapling is not installed; fallback extraction disabled")
            return ExtractedContent(
                title=self._clean_title(title or self._extract_title_from_html(html)),
                author=author,
                date=date,
                raw_html=html,
                method=f"{method}_unavailable",
            )

        try:
            doc = Selector(html)
            for css in self.FALLBACK_SELECTORS:
                element = next(iter(doc.css(css)), None)
                if not element:
                    continue
                raw_text = element.get_all_text() if hasattr(element, "get_all_text") else element.text
                content = self._clean_text(str(raw_text or ""))
                if len(content) >= MIN_CONTENT_LENGTH:
                    return ExtractedContent(
                        title=self._clean_title(title or self._extract_title_from_html(html)),
                        content=content,
                        author=author,
                        date=date,
                        raw_html=html,
                        method=method,
                    )
        except Exception as exc:
            logger.warning("Scrapling fallback extraction failed: %s", exc)
            method = f"{method}_error"

        return ExtractedContent(
            title=self._clean_title(title or self._extract_title_from_html(html)),
            author=author,
            date=date,
            raw_html=html,
            method=method,
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
    def _clean_text(text: str) -> str:
        text = re.sub(r"\s+", " ", text or "").strip()
        return text

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
