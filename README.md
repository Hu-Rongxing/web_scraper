# web_scraper

`web_scraper` is a Python package for article extraction and list-page link discovery.

## What it does

- `ContentExtractor` extracts complete article bodies from reader/plain-text responses, structured JSON-LD/front-end state, `trafilatura`, then Scrapling-based text cleanup.
- `LinkExtractor` extracts article links from list pages with Scrapling DOM selectors and optional article URL/title filters.
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
        links = await fetcher.fetch_links(
            "https://example.com/news",
            css=["a.headline[href]", "article a[href]"],
            require_url_pattern=r"/news/\d{4}/\d{2}/\d{2}/[^/]+\.html$",
            reject_url_contains=["/newsletter/", "/video/"],
        )
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

## v7-Learned Extraction Guards

The extractor applies lessons learned from separate v7 monitor probes without any runtime dependency on that project:

- JSON-LD is accepted as full text only when it exposes `articleBody`.
- Next.js/Nuxt/Apollo-style script state can provide complete bodies from keys such as `articleBody`, `fullText`, `nodeTree`, `paragraphs`, or `blocks`.
- Reader warning shells, login prompts, paywall previews, and challenge pages remain rejected diagnostics instead of article content.
- List-page discovery can require terminal article URL patterns and reject known channel roots, newsletters, videos, or promotional titles before detail fetches are created.

## Notes

- `pyproject.toml` uses `src` layout imports.
- The live diagnostic scripts under `test/` may hit external sites and take longer to run.
- Repository-specific agent rules live in `AGENT_GUIDELINES.md`.
