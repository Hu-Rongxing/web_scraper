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

### Pipeline Architecture

```
URL → P1(HTTP轻量) → P2(基础浏览器) → P3(高防护) → P4(付费墙) → P5(反封锁) → 标记失败
```

See [AGENT_GUIDELINES.md](AGENT_GUIDELINES.md) for mandatory rules all agents must follow.

## Key Dependencies

| Package | Role | Docs |
|---------|------|------|
| **curl_cffi** | P1 HTTP with browser TLS fingerprint | https://github.com/lexiforest/curl_cffi |
| **Scrapling** | P1 Fetcher + DOM parsing | https://scrapling.readthedocs.io/en/latest/ |
| **CloakBrowser** | P2/P3/P4 anti-detection browser | https://cloakbrowser.dev/ |
| **Bypass Paywalls Clean** | P4 paywall bypass extension | https://gitflic.ru/project/magnolia1234/bypass-paywalls-chrome-clean |
| **trafilatura** | Content extraction | https://trafilatura.readthedocs.io/ |
| **nodriver** | Pipeline 6 fallback (real Chrome) | https://ultrafunkamsterdam.github.io/nodriver/ |

## Repository Layout

```text
.
|-- __init__.py                # public API exports
|-- content_extractor.py       # trafilatura + Scrapling fallback
|-- link_extractor.py          # Scrapling DOM link extraction
|-- fetchers/                  # public async fetch facade
|-- pipelines/                 # fetch/render/degradation managers
|   |-- pipeline.py            # 5-level pipeline scheduler
|   |-- anti_block.py          # bypass strategies (archive, cache, etc.)
|   |-- rss_validator.py       # RSS sync validation
|   `-- pipeline5.py           # nodriver fallback
|-- proxies/                   # proxy pool implementations
|-- browser_pool.py            # Pool A/B/C CloakBrowser pools
|-- models.py                  # result models
|-- config.py                  # runtime configuration
|-- test/                      # contract tests and live diagnostics
|-- examples/                  # public-API integration examples
|-- docs/                      # testing and verification notes
`-- AGENT_GUIDELINES.md        # mandatory rules for agents
```

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
