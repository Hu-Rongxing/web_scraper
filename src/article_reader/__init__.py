# -*- coding: utf-8 -*-
"""article_reader public API.

Article extraction uses trafilatura with Scrapling fallback. List-page link
discovery is handled by Scrapling through LinkExtractor / SmartFetcher.fetch_links().
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

__version__ = "3.1.0"

_EXPORTS = {
    "BaseFetcher": ("article_reader.fetchers", "BaseFetcher"),
    "SmartFetcher": ("article_reader.fetchers.smart", "SmartFetcher"),
    "ArticleReader": ("article_reader.fetchers.smart", "SmartFetcher"),
    "PluginManager": ("article_reader.plugin_manager", "PluginManager"),
    "ExtractStrategy": ("article_reader.config", "ExtractStrategy"),
    "PipelineManager": ("article_reader.pipelines", "PipelineManager"),
    "PipelineLevel": ("article_reader.pipelines", "PipelineLevel"),
    "Pipeline5Manager": ("article_reader.pipelines", "Pipeline5Manager"),
    "FetchResult": ("article_reader.models", "FetchResult"),
    "PipelineResult": ("article_reader.models", "PipelineResult"),
    "Pipeline5Result": ("article_reader.models", "Pipeline5Result"),
    "PipelineProxyPool": ("article_reader.proxies", "PipelineProxyPool"),
    "ResidentialRotatingPool": ("article_reader.proxies", "ResidentialRotatingPool"),
    "StaticBoundPool": ("article_reader.proxies", "StaticBoundPool"),
    "ContentExtractor": ("article_reader.content_extractor", "ContentExtractor"),
    "ExtractedContent": ("article_reader.content_extractor", "ExtractedContent"),
    "ExtractedLink": ("article_reader.link_extractor", "ExtractedLink"),
    "LinkExtractor": ("article_reader.link_extractor", "LinkExtractor"),
    "WallDetector": ("article_reader.pipelines", "WallDetector"),
    "URLTransformer": ("article_reader.pipelines", "URLTransformer"),
    "BypassExecutor": ("article_reader.pipelines", "BypassExecutor"),
    "AdvancedBypass": ("article_reader.pipelines", "AdvancedBypass"),
    "BypassMethod": ("article_reader.pipelines", "BypassMethod"),
    "BypassResult": ("article_reader.pipelines", "BypassResult"),
    "RSSValidator": ("article_reader.pipelines", "RSSValidator"),
    "RSSValidationResult": ("article_reader.pipelines", "RSSValidationResult"),
    "ArticleInfo": ("article_reader.pipelines", "ArticleInfo"),
    "RSSPolicy": ("article_reader.pipelines", "RSSPolicy"),
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> Any:
    try:
        module_name, attr_name = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(f"module 'article_reader' has no attribute {name!r}") from exc

    value = getattr(import_module(module_name), attr_name)
    globals()[name] = value
    return value
