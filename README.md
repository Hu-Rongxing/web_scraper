# web_scraper

`web_scraper` is a Python package for article extraction and list-page link discovery.

## What it does

- `ContentExtractor` extracts article text with `trafilatura`, then falls back to Scrapling-based text cleanup.
- `LinkExtractor` extracts article links from list pages with Scrapling DOM selectors.
- `SmartFetcher` wraps the pipeline stack for fetching, rendering, proxy use, and fallback handling.
- `PipelineManager` tries browser-like HTTP clients first, then lazy browser pools, then reader/archive/AMP/print/referer fallbacks with per-method diagnostics.

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

## v7 Failure Sample Probe

`examples/probe_v7_failed_sites.py` tests representative URLs that have failed in the separate `monitor_v7` project. The script is standalone inside `web_scraper`: it copies URLs as external test inputs and does not import or read `monitor_v7` code/config at runtime.

```bash
python examples/probe_v7_failed_sites.py
python examples/probe_v7_failed_sites.py --site wsj --site marketwatch
python examples/probe_v7_failed_sites.py --site wsj --timeout-sec 20
```

Reports are written to `docs/probe-results/`.

## Notes

- `pyproject.toml` uses `src` layout imports.
- The live diagnostic scripts under `test/` may hit external sites and take longer to run.
- Repository-specific agent rules live in `AGENT_GUIDELINES.md`.
