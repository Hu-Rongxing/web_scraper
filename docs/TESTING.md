# Testing Guide

This document describes the checks for the refactored article_reader extraction boundary.

## Fast Contract Tests

```bash
python -m pytest article_reader/test/test_refactor_contract.py -q
```

These tests verify:

- `ContentExtractor` extracts article details through trafilatura.
- Unsupported `extract_strategy` values normalize to trafilatura.
- `LinkExtractor` extracts list-page links through Scrapling DOM parsing.
- Proxy pool contracts still hold.
- Pipeline level public constants remain stable.

## Import Check

```bash
python -c "from article_reader import BaseFetcher, SmartFetcher, ContentExtractor, LinkExtractor, ExtractStrategy; print('exports ok')"
```

## Compile Check

```bash
python -m compileall article_reader
```

This catches syntax errors across package code and local test scripts.

## Network Tests

The broader scripts under `article_reader/test/` may perform live network, browser, or proxy work. Run them only in an environment where those dependencies are configured.

Common examples:

```bash
python article_reader/test/test_4sites.py
python article_reader/test/test_proxy_sites.py
python article_reader/test/analyze_links.py
```

## Expected Engine Boundary

After the refactor:

- Article detail extraction is handled by trafilatura.
- List-page link extraction is handled by Scrapling selectors.
- The package should not expose production article extraction strategies named `raw_html`, `raw_text`, `selector`, or `readability`.
