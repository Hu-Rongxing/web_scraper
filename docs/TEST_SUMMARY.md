# Test Summary

## Stable Contract Suite

The primary local suite is:

```bash
python -m pytest test/test_refactor_contract.py -q
```

Expected result:

```text
8 passed
```

This suite is intentionally independent of live websites, browsers, proxy pools, and local profiles.

## Current Extraction Contract

- `ContentExtractor` uses trafilatura for article details and Scrapling DOM text as fallback.
- `LinkExtractor` uses Scrapling DOM selectors for list-page links.
- `SmartFetcher.fetch_links()` is the public list extraction entry point.
- `extract_strategy` remains compatible but normalizes unsupported values to trafilatura.

## Integration Coverage

Live diagnostic scripts remain under `test/`. They are useful for browser, proxy, and site-specific validation but are not part of the fast contract gate.

Reports and captures belong under `test/output/` and are not committed.
