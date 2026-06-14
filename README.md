# article_reader

`article_reader` is a focused Python package for news list discovery and article detail extraction.

The project is intentionally scoped to two extraction engines:

- Article detail text: `trafilatura`, with Scrapling DOM text fallback when trafilatura is unavailable, errors, or returns too little text
- News/list links: Scrapling DOM selectors through `LinkExtractor`

Fetching, rendering, proxy assignment, and pipeline degradation remain in the existing pipeline layer. The extraction layer stays small so it is easier to test and replace internally without changing callers.

## Public API

```python
from article_reader import ContentExtractor, LinkExtractor, SmartFetcher
```

### Extract Article Details

```python
from article_reader import ContentExtractor

result = ContentExtractor().extract(html, "https://example.com/article")

print(result.title)
print(result.content)
print(result.method)
```

`ContentExtractor` returns `ExtractedContent`:

- `title`
- `content`
- `author`
- `date`
- `summary`
- `raw_html`
- `method`

The primary production article extraction strategy is `trafilatura`. Scrapling is the built-in fallback. The `extract_strategy` argument is retained for compatibility; unsupported values are normalized to `trafilatura`.

### Extract List Links

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

`LinkExtractor` returns `ExtractedLink` objects:

- `url`
- `title`

### Fetch Through Pipelines

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
`SmartFetcher.fetch_links()` fetches a list page and extracts links from the rendered HTML.

## Repository Layout

```text
.
|-- content_extractor.py      # trafilatura article extraction with Scrapling fallback
|-- link_extractor.py         # Scrapling DOM link extraction
|-- fetchers/
|   `-- smart.py              # public async fetch facade
|-- pipelines/                # fetch/render/degradation managers
|-- proxies/                  # proxy pool implementations
|-- examples/                 # runnable examples
|-- test/                     # tests and integration diagnostics
|   |-- output/               # generated test reports, ignored
|   `-- output_paths.py       # shared output path helper
|-- docs/                     # testing and verification notes
|-- models.py                 # result models
`-- config.py                 # runtime configuration
```

Generated outputs, browser profiles, screenshots, HTML captures, and test reports are ignored by default.

## Quick Verification

Run from this repository root:

```bash
python -m pytest test/test_refactor_contract.py -q
python -m py_compile content_extractor.py link_extractor.py fetchers/smart.py __init__.py
```

Optional import check:

```bash
python -c "from article_reader import SmartFetcher, ContentExtractor, LinkExtractor; print('ok')"
```

## Integration Tests

Most files under `test/` are live-site diagnostics. They can require network access, a local browser, proxy configuration, or long timeouts.

Examples:

```bash
python test/test_4sites.py
python test/test_proxy_sites.py
python test/test_comprehensive_links.py
```

Integration test output is written under `test/output/` and is not committed.
