# Test Summary

## Stable Local Suite

The primary local gate is:

```bash
python -m compileall src test examples
python -m pytest test/test_refactor_contract.py -q
python -m pytest test/test_bypass.py -q
```

Expected pytest result:

```text
8 passed in test_refactor_contract.py
3 passed in test_bypass.py
```

This suite is independent of live websites, browsers, proxy pools, and local profiles.

## Current Extraction Contract

- `ContentExtractor` uses trafilatura for article details and Scrapling DOM text as fallback.
- `LinkExtractor` uses Scrapling DOM selectors for list-page links.
- `SmartFetcher.fetch_links()` is the public list extraction entry point.
- `extract_strategy` remains compatible but normalizes unsupported values to trafilatura.
- `PipelineManager` keeps the five-level degradation contract and now uses lazy browser pools so HTTP/reader probes do not launch browsers until render paths are needed.
- Pipeline 5 records per-method fallback diagnostics for Jina reader variants, AMP/print variants, referer variants, archives, and cache attempts.

## Integration Coverage

Live diagnostic scripts remain under `test/` and public-API examples remain under `examples/`. They are useful for browser, proxy, and site-specific validation but are not part of the fast local gate.

Reports and captures belong under `test/output/` and are not committed.

The v7 failure sample probe writes committed-code-independent reports under `docs/probe-results/` for manual review.
