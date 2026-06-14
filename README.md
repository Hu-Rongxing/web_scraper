# web_scraper

`web_scraper` is a Python package for article extraction and list-page link discovery.

## What it does

- `ContentExtractor` extracts article text with `trafilatura`, then falls back to Scrapling-based text cleanup.
- `LinkExtractor` extracts article links from list pages with Scrapling DOM selectors.
- `SmartFetcher` wraps the pipeline stack for fetching, rendering, proxy use, and fallback handling.

## Public API

```python
from web_scraper import ContentExtractor, LinkExtractor, SmartFetcher
```

## Quick Start

```python
import asyncio
from web_scraper import SmartFetcher


async def main():
    async with SmartFetcher() as fetcher:
        article = await fetcher.fetch("https://example.com/article")
        links = await fetcher.fetch_links("https://example.com/news")
        print(article.title)
        print(len(article.content))
        print(len(links))


asyncio.run(main())
```

## Package Layout

```text
src/web_scraper/
  __init__.py
  config.py
  content_extractor.py
  link_extractor.py
  fetchers/
  pipelines/
  proxies/
  browser_pool.py
  plugin_manager.py
  retry.py
```

## Local Checks

```bash
python -m compileall src test examples
python -m pytest test/test_refactor_contract.py -q
python -m pytest test/test_bypass.py -q
```

## Notes

- `pyproject.toml` uses `src` layout imports.
- The live diagnostic scripts under `test/` may hit external sites and take longer to run.
- Repository-specific agent rules live in `AGENT_GUIDELINES.md`.
