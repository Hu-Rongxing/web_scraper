# -*- coding: utf-8 -*-
"""Fetcher interfaces."""

from ..models import FetchResult


class BaseFetcher:
    """Base fetcher interface."""

    async def fetch(self, url: str, **opts) -> FetchResult:
        raise NotImplementedError

    async def fetch_many(self, urls: list[str], **opts) -> list[FetchResult]:
        raise NotImplementedError


__all__ = ["BaseFetcher", "FetchResult"]
