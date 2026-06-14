# Test Summary

## Current Scope

The refactor closes article_reader content extraction to two focused paths:

- Article detail extraction: trafilatura.
- News list link extraction: Scrapling DOM parsing through `LinkExtractor`.

`extract_strategy` is retained for compatibility, but unsupported values are normalized to trafilatura.

## Verified Commands

```bash
python -c "from article_reader import BaseFetcher, SmartFetcher, ContentExtractor, LinkExtractor, ExtractStrategy; print('exports ok')"
python -m pytest article_reader/test/test_refactor_contract.py -q
```

Expected focused test result:

```text
7 passed
```

## Remaining External Dependencies

Some legacy integration scripts still require local browser, proxy, or live network configuration. They are useful for environment validation, but they are not required for the extraction engine contract.

## Refactor Result

- `ContentExtractor` is trafilatura-only.
- `LinkExtractor` owns list-page link extraction.
- `SmartFetcher.fetch_links()` provides a public list extraction entry point.
- Public exports include `ContentExtractor`, `LinkExtractor`, `ExtractedContent`, and `ExtractedLink`.
