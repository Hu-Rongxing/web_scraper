# -*- coding: utf-8 -*-
"""Pipeline package public exports.

Exports are resolved lazily so helper modules can be used without importing
browser-pool code.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
    "PipelineLevel": ("web_scraper.pipelines.levels", "PipelineLevel"),
    "PipelineManager": ("web_scraper.pipelines.pipeline", "PipelineManager"),
    "Pipeline5Manager": ("web_scraper.pipelines.pipeline5", "Pipeline5Manager"),
    "PipelineResult": ("web_scraper.models", "PipelineResult"),
    "Pipeline5Result": ("web_scraper.models", "Pipeline5Result"),
    "WallDetector": ("web_scraper.pipelines.anti_block", "WallDetector"),
    "URLTransformer": ("web_scraper.pipelines.anti_block", "URLTransformer"),
    "BypassExecutor": ("web_scraper.pipelines.anti_block", "BypassExecutor"),
    "AdvancedBypass": ("web_scraper.pipelines.anti_block", "AdvancedBypass"),
    "BypassMethod": ("web_scraper.pipelines.anti_block", "BypassMethod"),
    "BypassResult": ("web_scraper.pipelines.anti_block", "BypassResult"),
    "RSSValidator": ("web_scraper.pipelines.rss_validator", "RSSValidator"),
    "RSSValidationResult": ("web_scraper.pipelines.rss_validator", "RSSValidationResult"),
    "ArticleInfo": ("web_scraper.pipelines.rss_validator", "ArticleInfo"),
    "RSSPolicy": ("web_scraper.pipelines.rss_validator", "RSSPolicy"),
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> Any:
    try:
        module_name, attr_name = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(f"module 'web_scraper.pipelines' has no attribute {name!r}") from exc

    value = getattr(import_module(module_name), attr_name)
    globals()[name] = value
    return value
