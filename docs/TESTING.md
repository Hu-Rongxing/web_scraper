# Testing Guide

Run commands from the `article_reader` repository root.

## Fast Local Gate

```bash
python -m compileall src test examples
python -m pytest test/test_refactor_contract.py -q
python -m pytest test/test_bypass.py -q
```

The fast gate covers:

- package imports from the `src/` layout
- trafilatura article extraction with Scrapling fallback
- compatibility normalization for unsupported extraction strategies
- Scrapling-based list link extraction
- proxy pool behavior
- pipeline level public constants
- wall detection and RSS validation helper behavior

`pyproject.toml` configures `pytest` with `pythonpath = ["src"]`, so tests can import `article_reader` directly.

## Import Check

```bash
python -c "from article_reader import BaseFetcher, SmartFetcher, ContentExtractor, LinkExtractor, ExtractStrategy; print('exports ok')"
```

## Live Diagnostics

Most files under `test/` beyond the fast gate are live-site diagnostics. They may launch browsers, hit real websites, use proxies, or take several minutes.

Common scripts:

```bash
python test/test_4sites.py
python test/test_proxy_sites.py
python test/test_comprehensive_links.py
python test/test_wsj_optimized.py
```

Generated reports should use `test/output/`. That directory is ignored.

## Linting

```bash
ruff check .
```

Some legacy diagnostic scripts are intentionally broader than the contract suite. Treat lint findings there as cleanup work unless the current task targets them.

## Codegraph

Update the index after structural changes:

```bash
codegraph build . --no-incremental
```
