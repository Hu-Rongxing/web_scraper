# article_reader

article_reader is a news list and article detail extraction package.

The current extraction boundary is intentionally narrow:

- Article detail extraction uses `trafilatura` only.
- News list and link extraction uses Scrapling DOM parsing through `LinkExtractor`.
- Fetching and degradation are handled by the existing pipeline manager.
- `extract_strategy` remains as a compatibility parameter, but unsupported values are normalized to `trafilatura`.

## Public API

```python
from article_reader import ContentExtractor, LinkExtractor, SmartFetcher
```

### Article Detail Extraction

```python
from article_reader import ContentExtractor

html = "<html><body><article><h1>Title</h1><p>Body...</p></article></body></html>"
result = ContentExtractor().extract(html, "https://example.com/article")

print(result.title)
print(result.content)
print(result.method)
```

`ContentExtractor` returns an `ExtractedContent` object with normalized fields:

- `title`
- `content`
- `author`
- `date`
- `summary`
- `raw_html`
- `method`

Supported extraction method values are based on trafilatura state:

- `trafilatura`
- `trafilatura_short`
- `trafilatura_empty`
- `trafilatura_unavailable`
- `trafilatura_error`

### News List Extraction

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

`LinkExtractor` uses Scrapling selectors and returns `ExtractedLink` objects:

- `url`
- `title`

### Unified Fetcher

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

`SmartFetcher.fetch()` returns article detail content.
`SmartFetcher.fetch_links()` returns list-page links from the fetched HTML.

## Architecture

The package is split by responsibility:

```text
article_reader/
  content_extractor.py     # trafilatura-only article extraction
  link_extractor.py        # Scrapling DOM link extraction
  fetchers/
    smart.py               # public async fetcher facade
  pipelines/               # fetch, render, degradation, bypass managers
  proxies/                 # proxy pool implementations
  models.py                # result models
  config.py                # runtime configuration
```

## Engine Boundary

Production content extraction is closed to two engines:

- `trafilatura` for article detail text.
- `scrapling.Selector` for list-page DOM link extraction.

The package no longer exposes multiple article extraction strategies such as `raw_html`, `raw_text`, `selector`, or `readability`.

## Verification

Run the focused contract tests:

```bash
python -m pytest article_reader/test/test_refactor_contract.py -q
```

Compile the package:

```bash
python -m compileall article_reader
```

Optional import check:

```bash
python -c "from article_reader import SmartFetcher, ContentExtractor, LinkExtractor; print('ok')"
```

## Notes

Some integration tests depend on local browser, proxy, or network configuration. The focused contract tests are the fastest way to verify the extraction boundary without those external dependencies.
