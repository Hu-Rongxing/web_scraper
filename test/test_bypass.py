# -*- coding: utf-8 -*-
"""Lightweight tests for wall detection and RSS validation helpers."""

import asyncio
import sys
from datetime import datetime, timedelta

from path_setup import add_src_to_path

add_src_to_path()

from article_reader import ArticleInfo, RSSValidator, URLTransformer, WallDetector


def test_wall_detection() -> None:
    paywall_html = """
    <html><body>
      <article><p>Some content here...</p></article>
      <div class="paywall">
        <p>Subscribe now to continue reading</p>
        <script src="https://cdn.piano.io/paywall.js"></script>
      </div>
    </body></html>
    """
    login_html = """
    <html><body>
      <div class="login-wall">
        <p>Please log in to continue reading</p>
        <form action="/login"></form>
      </div>
    </body></html>
    """
    truncated_html = """
    <html><body>
      <article><p>This is a very long article that goes on and on...</p></article>
      <!-- paywall -->
    </body></html>
    """

    assert WallDetector.detect_paywall(paywall_html)
    assert WallDetector.detect_login_wall(login_html)
    assert WallDetector.detect_truncation(truncated_html, "short")
    assert WallDetector.detect_wall_type(paywall_html, "") == "paywall"
    assert WallDetector.detect_wall_type(login_html, "") == "login_wall"
    assert WallDetector.detect_wall_type(truncated_html, "short") == "truncated"


def test_url_transformation() -> None:
    url = "https://www.wsj.com/articles/test-article-123"

    assert "web.archive.org" in URLTransformer.to_archive_org(url)
    assert "webcache.googleusercontent.com" in URLTransformer.to_google_cache(url)
    assert "archive.ph" in URLTransformer.to_archive_today(url)
    assert URLTransformer.to_amp_version(url)
    assert URLTransformer.to_print_version(url)


def test_rss_validation() -> None:
    asyncio.run(_validate_rss())


async def _validate_rss() -> None:
    validator = RSSValidator()
    now = datetime.now()
    rss_articles = [
        ArticleInfo("Test Article 1", "https://example.com/article1", now - timedelta(seconds=10)),
        ArticleInfo("Test Article 2", "https://example.com/article2", now - timedelta(seconds=20)),
    ]
    original_articles = [
        ArticleInfo("Test Article 1", "https://example.com/article1", now - timedelta(seconds=5)),
        ArticleInfo("Test Article 2", "https://example.com/article2", now - timedelta(seconds=15)),
    ]

    result = await validator.validate(
        rss_url="https://example.com/rss",
        original_url="https://example.com",
        rss_articles=rss_articles,
        original_articles=original_articles,
    )

    assert result.is_valid
    assert result.sync_delay_seconds <= 30
    assert result.article_match_ratio >= 0.9


def main() -> None:
    test_wall_detection()
    test_url_transformation()
    test_rss_validation()
    print("bypass helper tests passed")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"test failed: {exc}")
        sys.exit(1)
