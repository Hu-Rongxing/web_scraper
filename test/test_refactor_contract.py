# -*- coding: utf-8 -*-

import asyncio

import pytest
from path_setup import add_src_to_path

add_src_to_path()

import web_scraper.content_extractor as content_extractor
from web_scraper import (
    ContentExtractor,
    ExtractedContent,
    LinkExtractor,
    PipelineLevel,
    PipelineProxyPool,
    ResidentialRotatingPool,
    StaticBoundPool,
)
from web_scraper.pipelines.pipeline import PipelineManager


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


def test_content_extractor_accepts_reader_plain_text():
    reader_text = (
        "Title: Example Story\n"
        "URL Source: https://example.com/story\n"
        "Markdown Content:\n\n"
        f"{LONG_PARAGRAPH}\n\n{LONG_PARAGRAPH}\n"
    )
    result = ContentExtractor(strategy="trafilatura").extract(reader_text, "https://example.com/story")

    assert result.method == "reader_plain_text"
    assert "article body text" in result.content


def test_content_extractor_rejects_reader_paywall_teaser():
    reader_text = (
        "Title: Example Story\n"
        "URL Source: https://example.com/story\n"
        "Markdown Content:\n\n"
        "Continue with a free trial to read this story.\n"
        f"{LONG_PARAGRAPH}\n\n{LONG_PARAGRAPH}\n"
    )
    result = ContentExtractor(strategy="trafilatura").extract(reader_text, "https://example.com/story")

    assert result.method == "reader_plain_text_rejected"
    assert result.content == ""


def test_content_extractor_prefers_json_ld_article_body():
    html = f"""
    <html>
      <head>
        <script type="application/ld+json">
        {{
          "@context": "https://schema.org",
          "@type": "NewsArticle",
          "headline": "Structured Headline",
          "datePublished": "2026-06-15T08:00:00Z",
          "description": "Short teaser only.",
          "articleBody": "{LONG_PARAGRAPH}"
        }}
        </script>
      </head>
      <body><article><p>Short body.</p></article></body>
    </html>
    """
    result = ContentExtractor(strategy="trafilatura").extract(html, "https://example.com/structured")

    assert result.method == "json_ld"
    assert result.title == "Structured Headline"
    assert "article body text" in result.content
    assert result.date == "2026-06-15T08:00:00Z"


def test_content_extractor_does_not_accept_json_ld_description_as_body(monkeypatch):
    if content_extractor.trafilatura is None:
        pytest.skip("trafilatura is not installed")

    html = f"""
    <html>
      <head>
        <title>Description Only</title>
        <script type="application/ld+json">
        {{
          "@context": "https://schema.org",
          "@type": "NewsArticle",
          "headline": "Description Only",
          "description": "{LONG_PARAGRAPH}"
        }}
        </script>
      </head>
      <body><main><p>Short teaser.</p></main></body>
    </html>
    """
    monkeypatch.setattr(content_extractor.trafilatura, "extract", lambda *args, **kwargs: "")
    monkeypatch.setattr(content_extractor.trafilatura, "extract_metadata", lambda *args, **kwargs: None)

    result = ContentExtractor(strategy="trafilatura").extract(html, "https://example.com/teaser")

    assert result.method == "trafilatura_short"
    assert result.content == ""


def test_content_extractor_reads_next_data_article_body():
    html = f"""
    <html>
      <head>
        <script id="__NEXT_DATA__" type="application/json">
        {{
          "props": {{
            "pageProps": {{
              "story": {{
                "title": "Next Data Story",
                "articleBody": "{LONG_PARAGRAPH}"
              }}
            }}
          }}
        }}
        </script>
      </head>
      <body><div id="__next"></div></body>
    </html>
    """
    result = ContentExtractor(strategy="trafilatura").extract(html, "https://example.com/next")

    assert result.method == "script_state:__next_data__"
    assert result.title == "Next Data Story"
    assert "article body text" in result.content


def test_pipeline_manager_jina_reader_variants():
    manager = PipelineManager()
    urls = manager._jina_reader_urls("https://www.ft.com/content/a7f4246d-9ae2-4f7b-90af-e5a53c52203b?foo=bar")

    assert urls[0].startswith("https://r.jina.ai/http://https://www.ft.com/content/")
    assert any("http://http://" in url for url in urls)
    assert any("http://https://" in url for url in urls)
    assert len(urls) == len(set(urls))


def test_pipeline_manager_jina_reader_variants_add_www_for_bare_domain():
    manager = PipelineManager()
    urls = manager._jina_reader_urls("https://economist.com/business/story")

    assert any("https://www.economist.com/business/story" in url for url in urls)
    assert any("http://www.economist.com/business/story" in url for url in urls)
    assert len(urls) == len(set(urls))


def test_pipeline_manager_reader_failure_detection():
    manager = PipelineManager()
    assert manager._is_reader_failure('{"code":451,"message":"Anonymous access to domain www.reuters.com blocked"}')
    assert manager._is_reader_failure("Warning: Target URL returned error 401")
    assert manager._is_reader_failure("Please enable JS and disable any ad blocker")
    assert manager._is_reader_failure("Title: Wayback Machine\nCalendar View\nSaved from example.com")
    assert not manager._is_reader_failure("Title: Example\nMarkdown Content:\n\nBody text only.")


def test_pipeline_manager_rejects_archive_search_shell():
    manager = PipelineManager()
    extracted = ExtractedContent(
        title="Wayback Machine",
        content="Calendar View Saved from example.com. " * 30,
    )

    error = manager._p5_quality_error(
        "https://www.wsj.com/finance/story",
        "https://web.archive.org/web/20240000000000*/https://www.wsj.com/finance/story",
        "archive_org",
        extracted,
    )

    assert error == "archive/search shell"


def test_pipeline_manager_rejects_short_archive_result():
    manager = PipelineManager()
    extracted = ExtractedContent(
        title="Source Story",
        content="wsj.com short archive snippet. " * 12,
    )

    error = manager._p5_quality_error(
        "https://www.wsj.com/finance/story",
        "https://web.archive.org/web/20240101000000/https://www.wsj.com/finance/story",
        "archive_org",
        extracted,
    )

    assert error.startswith("archive content too short")


def test_pipeline_manager_variant_urls():
    manager = PipelineManager()
    urls = manager._variant_urls("https://example.com/articles/story?x=1")

    assert "https://example.com/articles/story?x=1&amp=1" in urls
    assert "https://example.com/articles/story?x=1&view=print" in urls
    assert "https://example.com/amp/articles/story?x=1" in urls


def test_pipeline_manager_desktop_headers():
    manager = PipelineManager()
    headers = manager._desktop_headers("https://example.com/path")

    assert headers["User-Agent"]
    assert headers["Referer"] == "https://example.com/"
    assert "text/html" in headers["Accept"]


def test_link_extractor_uses_scrapling_dom():
    links = LinkExtractor().extract(
        '<a href="/a">First article headline</a><a href="https://other.test/b">Other</a>',
        "https://example.com/news",
        min_title_length=5,
    )

    assert len(links) == 1
    assert links[0].url == "https://example.com/a"
    assert links[0].title == "First article headline"


def test_link_extractor_filters_article_urls_and_titles():
    html = """
    <a class="headline" href="/news/2026/06/15/story.html">Valid article headline</a>
    <a class="headline" href="/news/">Channel root</a>
    <a class="headline" href="/newsletter/signup">Newsletter signup</a>
    <a class="fallback" href="/news/2026/06/15/second.html">Second article headline</a>
    """
    links = LinkExtractor().extract(
        html,
        "https://example.com/news",
        css=["a:not(", "a.headline[href]", "a.fallback[href]"],
        require_url_pattern=r"/news/\d{4}/\d{2}/\d{2}/[^/]+\.html$",
        reject_url_contains=["newsletter"],
        reject_title_patterns=[r"Channel root"],
        min_title_length=5,
    )

    assert [link.url for link in links] == [
        "https://example.com/news/2026/06/15/story.html",
        "https://example.com/news/2026/06/15/second.html",
    ]


def test_link_extractor_include_domains_allows_subdomains():
    html = """
    <a href="https://finance.jrj.com.cn/story.html">Finance headline</a>
    <a href="https://stock.jrj.com.cn/story.html">Stock headline</a>
    <a href="https://example.com/story.html">Other headline</a>
    """

    links = LinkExtractor().extract(
        html,
        "https://www.jrj.com.cn/",
        same_domain=False,
        include_domains=["jrj.com.cn"],
        min_title_length=5,
    )

    assert [link.url for link in links] == [
        "https://finance.jrj.com.cn/story.html",
        "https://stock.jrj.com.cn/story.html",
    ]


def test_pipeline_proxy_pool_round_robins_fixed_entries():
    asyncio.run(_test_pipeline_proxy_pool_round_robins_fixed_entries())


async def _test_pipeline_proxy_pool_round_robins_fixed_entries():
    pool = PipelineProxyPool(["http://proxy-a", "http://proxy-b"])

    assert await pool.acquire() == "http://proxy-a"
    assert await pool.acquire() == "http://proxy-b"
    assert await pool.acquire() == "http://proxy-a"
    assert pool.available_count == 2


def test_residential_pool_blacklists_after_repeated_failures():
    asyncio.run(_test_residential_pool_blacklists_after_repeated_failures())


async def _test_residential_pool_blacklists_after_repeated_failures():
    pool = ResidentialRotatingPool(["http://proxy-a"], max_fail_before_blacklist=2)

    assert await pool.acquire() == "http://proxy-a"
    await pool.release("http://proxy-a", success=False)
    assert pool.available_count == 1
    await pool.release("http://proxy-a", success=False)
    assert pool.available_count == 0


def test_static_bound_pool_keeps_context_binding_until_release():
    asyncio.run(_test_static_bound_pool_keeps_context_binding_until_release())


async def _test_static_bound_pool_keeps_context_binding_until_release():
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
