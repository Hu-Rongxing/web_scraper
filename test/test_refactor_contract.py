# -*- coding: utf-8 -*-

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import article_reader.content_extractor as content_extractor
from article_reader import (
    ContentExtractor,
    ExtractedContent,
    LinkExtractor,
    PipelineLevel,
    PipelineProxyPool,
    ResidentialRotatingPool,
    StaticBoundPool,
)


LONG_PARAGRAPH = "This is article body text for a local extraction contract. " * 12
HTML = f"""
<html>
  <head><title>Document Title</title></head>
  <body>
    <nav>Navigation noise</nav>
    <article>
      <h1>Article Heading</h1>
      <p>{LONG_PARAGRAPH}</p>
    </article>
  </body>
</html>
"""


def test_content_extractor_trafilatura_contract():
    result = ContentExtractor(strategy="trafilatura").extract(HTML, "https://example.com/a")

    assert isinstance(result, ExtractedContent)
    assert result.title == "Article Heading"
    assert "article body text" in result.content
    assert result.method == "trafilatura"


def test_content_extractor_normalizes_unsupported_strategy():
    result = ContentExtractor(strategy="selector").extract(HTML, "https://example.com/a")

    assert "article body text" in result.content
    assert result.method == "trafilatura"


def test_content_extractor_uses_scrapling_fallback_for_short_trafilatura_result(monkeypatch):
    if content_extractor.trafilatura is None:
        pytest.skip("trafilatura is not installed")

    noisy_html = f"""
    <html>
      <head><title>Fallback Title</title></head>
      <body>
        <article>
          <div>{LONG_PARAGRAPH}</div>
          <div>{LONG_PARAGRAPH}</div>
        </article>
      </body>
    </html>
    """

    monkeypatch.setattr(content_extractor.trafilatura, "extract", lambda *args, **kwargs: "")
    monkeypatch.setattr(content_extractor.trafilatura, "extract_metadata", lambda *args, **kwargs: None)

    result = ContentExtractor(strategy="trafilatura").extract(noisy_html, "https://example.com/fallback")

    assert "article body text" in result.content
    assert result.method == "scrapling_fallback_short"


def test_link_extractor_uses_scrapling_dom():
    links = LinkExtractor().extract(
        '<a href="/a">First article headline</a><a href="https://other.test/b">Other</a>',
        "https://example.com/news",
        min_title_length=5,
    )

    assert len(links) == 1
    assert links[0].url == "https://example.com/a"
    assert links[0].title == "First article headline"


@pytest.mark.asyncio
async def test_pipeline_proxy_pool_round_robins_fixed_entries():
    pool = PipelineProxyPool(["http://proxy-a", "http://proxy-b"])

    assert await pool.acquire() == "http://proxy-a"
    assert await pool.acquire() == "http://proxy-b"
    assert await pool.acquire() == "http://proxy-a"
    assert pool.available_count == 2


@pytest.mark.asyncio
async def test_residential_pool_blacklists_after_repeated_failures():
    pool = ResidentialRotatingPool(["http://proxy-a"], max_fail_before_blacklist=2)

    assert await pool.acquire() == "http://proxy-a"
    await pool.release("http://proxy-a", success=False)
    assert pool.available_count == 1
    await pool.release("http://proxy-a", success=False)
    assert pool.available_count == 0


@pytest.mark.asyncio
async def test_static_bound_pool_keeps_context_binding_until_release():
    pool = StaticBoundPool(["http://proxy-a"], pool_name="test")

    assert await pool.acquire_for_context("ctx-1") == "http://proxy-a"
    assert await pool.acquire_for_context("ctx-1") == "http://proxy-a"
    assert await pool.acquire_for_context("ctx-2") is None
    assert pool.bound_count == 1

    await pool.release_context("ctx-1")

    assert pool.bound_count == 0
    assert await pool.acquire_for_context("ctx-2") == "http://proxy-a"


def test_pipeline_level_contract():
    assert PipelineLevel.all_levels() == [1, 2, 3, 4]
    assert PipelineLevel.name(PipelineLevel.HTTP)
