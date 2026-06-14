#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import asyncio
import sys

from path_setup import add_src_to_path

add_src_to_path()

from web_scraper import Pipeline5Manager, PipelineLevel, PipelineManager  # noqa: E402


async def _run_pipeline(level: int | None = None) -> bool:
    manager = PipelineManager()
    await manager.start()
    try:
        result = await manager.fetch(
            url="https://httpbin.org/html",
            pipeline_level=level if level is not None else PipelineLevel.HTTP,
            extract_strategy="trafilatura",
            skip_browser=True,
            timeout=10,
        )
        return bool(result)
    finally:
        await manager.shutdown()


async def _run_pipeline5() -> bool:
    manager = Pipeline5Manager()
    await manager.start()
    try:
        result = await manager.fetch(
            url="https://httpbin.org/html",
            extract_strategy="trafilatura",
        )
        return bool(result)
    finally:
        await manager.shutdown()


def test_pipeline_1_sync():
    assert asyncio.run(_run_pipeline(PipelineLevel.HTTP))


def test_pipeline_2_sync():
    assert asyncio.run(_run_pipeline(PipelineLevel.BASIC_RENDER))


def test_pipeline_3_sync():
    assert asyncio.run(_run_pipeline(PipelineLevel.HIGH_PROTECT))


def test_pipeline_4_sync():
    assert asyncio.run(_run_pipeline(PipelineLevel.PAYWALL))


def test_pipeline_5_sync():
    assert asyncio.run(_run_pipeline5())


def test_auto_escalation_sync():
    assert asyncio.run(_run_pipeline(PipelineLevel.HTTP))


if __name__ == "__main__":
    success = asyncio.run(_run_pipeline(PipelineLevel.HTTP))
    sys.exit(0 if success else 1)
