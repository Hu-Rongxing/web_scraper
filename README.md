# article_reader

`article_reader` is a Python package for news-list discovery and article-detail extraction.

The extraction surface is intentionally small:

- Article details use `trafilatura` first, with Scrapling DOM text fallback.
- News/list links use Scrapling DOM selectors through `LinkExtractor`.
- Fetching, rendering, proxy assignment, and pipeline degradation stay behind `SmartFetcher`.

## Public API

```python
from article_reader import ContentExtractor, LinkExtractor, SmartFetcher
```

## Article Details

```python
from article_reader import ContentExtractor

result = ContentExtractor().extract(html, "https://example.com/article")

print(result.title)
print(result.content)
print(result.method)
```

`ContentExtractor` returns `ExtractedContent` with:

- `title`
- `content`
- `author`
- `date`
- `summary`
- `raw_html`
- `method`

The `extract_strategy` argument is kept for compatibility. Unsupported values are normalized to `trafilatura`.

## List Links

```python
from article_reader import LinkExtractor

links = LinkExtractor().extract(
    html,
    "https://example.com/news",
    css="a[href]",
    same_domain=True,
    min_title_length=5,
)
```

`LinkExtractor` returns `ExtractedLink` objects with:

- `url`
- `title`

## Pipeline Fetching

```python
import asyncio
from article_reader import SmartFetcher


async def main():
    async with SmartFetcher() as fetcher:
        article = await fetcher.fetch("https://example.com/article")
        links = await fetcher.fetch_links("https://example.com/news")
        print(article.title, len(article.content), len(links))


asyncio.run(main())
```

`SmartFetcher.fetch()` returns extracted article content.
`SmartFetcher.fetch_links()` fetches a list page and extracts links from the fetched HTML.

## Repository Layout

```text
.
|-- src/article_reader/        # package source
|   |-- content_extractor.py   # trafilatura + Scrapling fallback
|   |-- link_extractor.py      # Scrapling DOM link extraction
|   |-- fetchers/              # public async fetch facade
|   |-- pipelines/             # fetch/render/degradation managers
|   |-- proxies/               # proxy pool implementations
|   |-- models.py              # result models
|   `-- config.py              # runtime configuration
|-- test/                      # contract tests and live diagnostics
|-- examples/                  # public-API integration examples
|-- docs/                      # testing and verification notes
|-- tools/                     # reserved for repo maintenance helpers
|-- pyproject.toml             # pytest/ruff configuration
`-- .codegraph/                # codegraph index
```

Generated outputs, caches, browser profiles, screenshots, HTML captures, and test reports are ignored.

## Quick Verification

Run from the repository root:

```bash
python -m compileall src test examples
python -m pytest test/test_refactor_contract.py -q
python -m pytest test/test_bypass.py -q
```

Optional import check:

```bash
python -c "from article_reader import SmartFetcher, ContentExtractor, LinkExtractor; print('ok')"
```

## Examples

```bash
python examples/tencent_latest.py
python examples/economist_latest.py
python examples/wsj_latest.py
```

These scripts use the public API only. They are live-site checks, so results depend on network access and the target site response.

## Codegraph

Rebuild the project index after structural changes:

```bash
codegraph build . --no-incremental
```
