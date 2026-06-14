# -*- coding: utf-8 -*-
"""Pipeline package public exports.

Exports are resolved lazily so helper modules can be used without importing
browser-pool code.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
    "PipelineLevel": ("article_reader.pipelines.levels", "PipelineLevel"),
    "PipelineManager": ("article_reader.pipelines.pipeline", "PipelineManager"),
    "Pipeline5Manager": ("article_reader.pipelines.pipeline5", "Pipeline5Manager"),
    "PipelineResult": ("article_reader.models", "PipelineResult"),
    "Pipeline5Result": ("article_reader.models", "Pipeline5Result"),
    "WallDetector": ("article_reader.pipelines.anti_block", "WallDetector"),
    "URLTransformer": ("article_reader.pipelines.anti_block", "URLTransformer"),
    "BypassExecutor": ("article_reader.pipelines.anti_block", "BypassExecutor"),
    "AdvancedBypass": ("article_reader.pipelines.anti_block", "AdvancedBypass"),
    "BypassMethod": ("article_reader.pipelines.anti_block", "BypassMethod"),
    "BypassResult": ("article_reader.pipelines.anti_block", "BypassResult"),
    "RSSValidator": ("article_reader.pipelines.rss_validator", "RSSValidator"),
    "RSSValidationResult": ("article_reader.pipelines.rss_validator", "RSSValidationResult"),
    "ArticleInfo": ("article_reader.pipelines.rss_validator", "ArticleInfo"),
    "RSSPolicy": ("article_reader.pipelines.rss_validator", "RSSPolicy"),
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> Any:
    try:
        module_name, attr_name = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(f"module 'article_reader.pipelines' has no attribute {name!r}") from exc

    value = getattr(import_module(module_name), attr_name)
    globals()[name] = value
    return value
