# -*- coding: utf-8 -*-
"""
pipelines/ — 六级管线调度系统

管线 1→2→3→4→5 自动降级，管线 6 为 nodriver 兜底链路，需人工评估后启用。
管线 5 为反封锁突破，自动尝试 Archive/Cache/Reader Mode/Referer 等 12+ 种策略。
"""

from ..models import Pipeline5Result, PipelineResult
from .pipeline import PipelineLevel, PipelineManager
from .pipeline5 import Pipeline5Manager
from .anti_block import WallDetector, URLTransformer, BypassExecutor, AdvancedBypass, BypassMethod, BypassResult
from .rss_validator import RSSValidator, RSSValidationResult, ArticleInfo, RSSPolicy

__all__ = [
    "PipelineManager", "PipelineResult", "PipelineLevel",
    "Pipeline5Manager", "Pipeline5Result",
    # 反封锁突破
    "WallDetector", "URLTransformer", "BypassExecutor", "AdvancedBypass",
    "BypassMethod", "BypassResult",
    # RSS 同步验证
    "RSSValidator", "RSSValidationResult", "ArticleInfo", "RSSPolicy",
]
