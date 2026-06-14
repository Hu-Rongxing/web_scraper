# -*- coding: utf-8 -*-
"""List-page link extraction backed by Scrapling DOM parsing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable
from urllib.parse import urlparse

from .config import logger

try:
    from scrapling import Selector
except ImportError:  # pragma: no cover - depends on local environment
    Selector = None


@dataclass(frozen=True)
class ExtractedLink:
    url: str
    title: str = ""


class LinkExtractor:
    """Extract links from HTML with Scrapling selectors."""

    def extract(
        self,
        html: str,
        base_url: str,
        *,
        css: str = "a[href]",
        same_domain: bool = True,
        include_domains: Iterable[str] | None = None,
        min_title_length: int = 1,
        max_title_length: int = 240,
    ) -> list[ExtractedLink]:
        if not html:
            return []
        if Selector is None:
            logger.error("scrapling is not installed; link extraction disabled")
            return []

        base_domain = self._registrable_domain(urlparse(base_url).netloc)
        allowed_domains = tuple(include_domains or ())
        doc = Selector(html, url=base_url)
        links: list[ExtractedLink] = []
        seen: set[str] = set()

        for element in doc.css(css):
            href = element.attrib.get("href")
            if not href:
                continue

            full_url = element.urljoin(href)
            parsed = urlparse(full_url)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                continue

            parsed_domain = self._registrable_domain(parsed.netloc)
            if same_domain and base_domain and parsed_domain != base_domain:
                continue
            if allowed_domains and not any(parsed.netloc.endswith(d) for d in allowed_domains):
                continue

            clean_url = parsed._replace(query="", fragment="").geturl()
            if clean_url in seen:
                continue

            title = str(element.text or "").strip()
            if len(title) < min_title_length or len(title) > max_title_length:
                continue

            seen.add(clean_url)
            links.append(ExtractedLink(url=clean_url, title=title))

        return links

    @staticmethod
    def _registrable_domain(netloc: str) -> str:
        host = netloc.split("@")[-1].split(":")[0].lower()
        if host.startswith("www."):
            host = host[4:]
        return host
