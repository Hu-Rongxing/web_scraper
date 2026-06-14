# Agent Guidelines - web_scraper

All agents working on `web_scraper` must follow these rules.

## Core Rules

1. Prefer the original site first. Use RSS only after validation.
2. Do not skip the pipeline stack. Escalate in order:
   - P1 HTTP fetch
   - P2 basic render
   - P3 high-protection browser path
   - P4 paywall path
   - P5 bypass/fallback path
3. Record results, bypass method, and failure reason in logs.
4. Do not treat challenge pages, login walls, or teaser shells as article content.
5. Keep diagnostics reproducible.

## RSS Validation

RSS may be used only after `RSSValidator` confirms it is safe to rely on.

```python
from web_scraper import RSSValidator

validator = RSSValidator()
result = await validator.validate(rss_url, original_url, rss_articles, original_articles)

if not result.is_valid:
    url = original_url
```

## Logging

```python
logger.info("fetch url=%s pipeline=P%s method=%s", url, result.pipeline_level, result.method)
if result.meta.get("bypass_method"):
    logger.info("bypass=%s", result.meta["bypass_method"])
if not result.success:
    logger.error("failed url=%s error=%s", url, result.error)
```

## Dependencies

| Package | Role |
|---|---|
| `curl_cffi` | P1 HTTP with browser-like fingerprinting |
| `Scrapling` | Fetch and DOM parsing |
| `CloakBrowser` | Browser-based protection handling |
| `Bypass Paywalls Clean` | P4 paywall handling |
| `trafilatura` | Article extraction |
| `nodriver` | Real browser fallback |

## Repository Notes

- Public imports should use `web_scraper`.
- Repository docs live in `README.md` and `docs/`.
- Build or refresh the codegraph after structural changes.

## Current Location

`D:\trend_radar\web_scraper`
