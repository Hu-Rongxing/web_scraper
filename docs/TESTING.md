# Testing Guide

Run commands from the `D:/trend_radar/web_scraper` repository root.

## Fast Gate

```bash
python -m compileall src test examples
python -m pytest test/test_refactor_contract.py -q
python -m pytest test/test_bypass.py -q
```

This gate checks package imports, extraction contracts, link parsing, proxy pool behavior, pipeline constants, wall detection, and RSS validation helpers.

## Import Check

```bash
python -c "from web_scraper import SmartFetcher, ContentExtractor, LinkExtractor; print('ok')"
```

## Live Diagnostics

Most tests outside the fast gate are live-site diagnostics. They can launch browsers, use proxies, hit public sites, and take several minutes.

Common scripts:

```bash
python test/test_4sites.py
python test/test_proxy_sites.py
python test/test_comprehensive_links.py
python test/test_wsj_optimized.py
```

Generated reports and captured pages should stay under `test/output/`.

## Codegraph

Rebuild the local index after structural changes:

```bash
codegraph index .
```
