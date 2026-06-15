# -*- coding: utf-8 -*-
"""web_scraper public API.

Article extraction uses trafilatura with Scrapling fallback. List-page link
discovery is handled by Scrapling through LinkExtractor / SmartFetcher.fetch_links().
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

__version__ = "3.2.0"

_EXPORTS = {
    "BaseFetcher": ("web_scraper.fetchers", "BaseFetcher"),
    "SmartFetcher": ("web_scraper.fetchers.smart", "SmartFetcher"),
    "ArticleReader": ("web_scraper.fetchers.smart", "SmartFetcher"),
    "PluginManager": ("web_scraper.plugin_manager", "PluginManager"),
    "ExtractStrategy": ("web_scraper.config", "ExtractStrategy"),
    "PipelineManager": ("web_scraper.pipelines", "PipelineManager"),
    "PipelineLevel": ("web_scraper.pipelines", "PipelineLevel"),
    "Pipeline5Manager": ("web_scraper.pipelines", "Pipeline5Manager"),
    "FetchResult": ("web_scraper.models", "FetchResult"),
    "PipelineResult": ("web_scraper.models", "PipelineResult"),
    "Pipeline5Result": ("web_scraper.models", "Pipeline5Result"),
    "PipelineProxyPool": ("web_scraper.proxies", "PipelineProxyPool"),
    "ResidentialRotatingPool": ("web_scraper.proxies", "ResidentialRotatingPool"),
    "StaticBoundPool": ("web_scraper.proxies", "StaticBoundPool"),
    "ContentExtractor": ("web_scraper.content_extractor", "ContentExtractor"),
    "ExtractedContent": ("web_scraper.content_extractor", "ExtractedContent"),
    "ExtractedLink": ("web_scraper.link_extractor", "ExtractedLink"),
    "LinkExtractor": ("web_scraper.link_extractor", "LinkExtractor"),
    "WallDetector": ("web_scraper.pipelines", "WallDetector"),
    "URLTransformer": ("web_scraper.pipelines", "URLTransformer"),
    "BypassExecutor": ("web_scraper.pipelines", "BypassExecutor"),
    "AdvancedBypass": ("web_scraper.pipelines", "AdvancedBypass"),
    "BypassMethod": ("web_scraper.pipelines", "BypassMethod"),
    "BypassResult": ("web_scraper.pipelines", "BypassResult"),
    "RSSValidator": ("web_scraper.pipelines", "RSSValidator"),
    "RSSValidationResult": ("web_scraper.pipelines", "RSSValidationResult"),
    "ArticleInfo": ("web_scraper.pipelines", "ArticleInfo"),
    "RSSPolicy": ("web_scraper.pipelines", "RSSPolicy"),
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> Any:
    try:
        module_name, attr_name = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(f"module 'web_scraper' has no attribute {name!r}") from exc

    value = getattr(import_module(module_name), attr_name)
    globals()[name] = value
    return value
