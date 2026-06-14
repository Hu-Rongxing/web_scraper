# Testing Guide

Run commands from the `article_reader` repository root.

## Fast Checks

```bash
python -m pytest test/test_refactor_contract.py -q
python -m py_compile content_extractor.py link_extractor.py fetchers/smart.py __init__.py
```

The contract tests cover:

- trafilatura article extraction with Scrapling fallback
- compatibility normalization for unsupported `extract_strategy` values
- Scrapling-based list link extraction
- proxy pool behavior
- pipeline level public constants

## Optional Import Check

```bash
python -c "from article_reader import BaseFetcher, SmartFetcher, ContentExtractor, LinkExtractor, ExtractStrategy; print('exports ok')"
```

## Live Integration Scripts

The broader scripts in `test/` may launch browsers, hit live sites, use proxies, or take several minutes. Run them only when that environment is ready.

Common scripts:

```bash
python test/test_4sites.py
python test/test_proxy_sites.py
python test/test_comprehensive_links.py
python test/test_wsj_optimized.py
```

Generated reports should use `test/output/`. That directory is ignored.

## Linting

`ruff check .` currently reports legacy style issues in older diagnostics and browser/pipeline modules. Treat it as a backlog signal unless the current task explicitly includes a lint cleanup pass.

## Codegraph

Update the index after structural changes:

```bash
codegraph build . --no-incremental
```
