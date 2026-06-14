# -*- coding: utf-8 -*-
"""Shared result models for web_scraper."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class FetchResult:
    """Public fetch result returned by fetchers."""

    url: str
    final_url: str = ""
    title: str = ""
    content: str = ""
    html: str = ""
    author: Optional[str] = None
    date: Optional[str] = None
    summary: Optional[str] = None
    length: int = 0
    content_type: str = "page"
    method: str = ""
    success: bool = False
    error: Optional[str] = None
    elapsed_ms: float = 0.0
    meta: dict = field(default_factory=dict)


@dataclass
class PipelineResult:
    """Pipeline execution result."""

    url: str
    final_url: str = ""
    title: str = ""
    content: str = ""
    html: str = ""
    author: Optional[str] = None
    date: Optional[str] = None
    summary: Optional[str] = None
    length: int = 0
    content_type: str = "page"
    method: str = ""
    success: bool = False
    error: Optional[str] = None
    elapsed_ms: float = 0.0
    pipeline_level: int = 0
    meta: dict = field(default_factory=dict)


@dataclass
class Pipeline5Result(PipelineResult):
    """Pipeline 5 execution result."""

    pipeline_level: int = 5
