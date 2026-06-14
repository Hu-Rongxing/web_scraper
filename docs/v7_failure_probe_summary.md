# v7 Failure Probe Summary

This document records representative live probes against URLs that failed in the separate v7 monitor. The URLs are copied as external inputs. `web_scraper` does not import, read, or depend on `monitor_v7` runtime code or configuration.

## Probe Method

- Tool: `examples/probe_v7_failed_sites.py`
- Default mode: HTTP and reader/archive/variant fallbacks with browser paths skipped.
- Browser check: selective `--with-browser` run for WSJ.
- Report path for future runs: `docs/probe-results/`

## Observed Results

| Site | Result | Best observed method | Notes |
|---|---:|---|---|
| fitch | OK | `pipeline1:curl_cffi_chrome124` | Browser-like TLS fingerprint was enough to fetch usable content. |
| swift | OK | `pipeline1:scrapling_fetcher` | Scrapling Fetcher returned usable page content after direct origin instability. |
| ftchinese | OK | `pipeline1:httpx_http2` | HTTP/2 path returned extractable content even when another HTTP attempt saw 403. |
| wsj | blocked | none | Lightweight paths returned 401/403/challenge shells or timed out. A local browser probe also timed out in this environment. |
| wsj_cn | blocked | none | Similar Dow Jones challenge behavior to WSJ. |
| marketwatch | blocked | none | 401/403 or challenge shells from origin/reader paths. |
| economist | blocked | none | Public paths expose teaser/challenge behavior, not reliable article body. |
| project_syndicate | blocked | none | Sample URL returned 404 and then timed out through fallbacks. |
| omfif | blocked | none | Cloudflare 403/challenge behavior remained in lightweight probes. |
| hkej | blocked | none | Cloudflare 403/challenge behavior remained in lightweight probes. |
| spglobal | blocked | none | 403 behavior remained in local probes. |
| reuters | blocked | none | Origin/list URL remained blocked or timed out through tested paths. |

## Follow-Up Guidance

- Keep the improved generic fallback order in `PipelineManager`: browser-like HTTP, lazy browser pools, Jina reader variants, AMP/print variants, referer variants, archives, and cache attempts.
- For still-blocked Dow Jones and Reuters-family targets, future work should test authorized/licensed feeds, stable regional proxies, persistent browser sessions, and site-specific allowed mirrors.
- Do not weaken global success criteria: challenge pages, login prompts, paywall teasers, and reader warning shells must remain failed results.
