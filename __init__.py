# -*- coding: utf-8 -*-
"""article_reader public API.

Article extraction uses trafilatura with Scrapling fallback. List-page link
discovery is handled by Scrapling through LinkExtractor / SmartFetcher.fetch_links().
"""
__version__ = "3.1.0"

from .models import FetchResult, PipelineResult, Pipeline5Result
from .config import ExtractStrategy
from .content_extractor import ContentExtractor, ExtractedContent
from .link_extractor import ExtractedLink, LinkExtractor
from .proxies import PipelineProxyPool, ResidentialRotatingPool, StaticBoundPool
from .pipelines import (
    PipelineManager, PipelineLevel,
    Pipeline5Manager,
    WallDetector, URLTransformer, BypassExecutor, AdvancedBypass,
    BypassMethod, BypassResult,
    RSSValidator, RSSValidationResult, ArticleInfo, RSSPolicy,
)
from .fetchers import BaseFetcher
from .fetchers.smart import SmartFetcher

__all__ = [
    "BaseFetcher",
    "SmartFetcher",
    "ExtractStrategy",
    "PipelineManager",
    "PipelineLevel",
    "Pipeline5Manager",
    "FetchResult",
    "PipelineResult",
    "Pipeline5Result",
    "PipelineProxyPool",
    "ResidentialRotatingPool",
    "StaticBoundPool",
    "ContentExtractor",
    "ExtractedContent",
    "ExtractedLink",
    "LinkExtractor",
    "WallDetector",
    "URLTransformer",
    "BypassExecutor",
    "AdvancedBypass",
    "BypassMethod",
    "BypassResult",
    "RSSValidator",
    "RSSValidationResult",
    "ArticleInfo",
    "RSSPolicy",
]
