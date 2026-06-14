# article_reader Comprehensive Link Test Report

**Date:** 2026-06-14 09:20:45

## Summary

- **Total URLs:** 32
- **Success:** 26 (81.2%)
- **Failed:** 6 (18.8%)

## Pipeline Distribution

| Pipeline | Count |
|----------|-------|
| P1 | 5 |
| P4 | 21 |

## Detailed Results

| # | Name | Status | Pipeline | Method | Time | Content |
|---|------|--------|----------|--------|------|--------|
| 1 | yahoo_finance | ✅ | P1 | pipeline1:scrapling_fetch | 3241ms | 223 chars |
| 2 | forbes | ✅ | P4 | pipeline4:pool_c_bpc | 28100ms | 8559 chars |
| 3 | bloomberg_1 | ✅ | P4 | pipeline4:pool_c_bpc | 71747ms | 397 chars |
| 4 | bloomberg_2 | ✅ | P4 | pipeline4:pool_c_bpc | 83876ms | 596 chars |
| 5 | sina_finance | ✅ | P4 | pipeline4:pool_c_bpc | 38804ms | 7088 chars |
| 6 | wsj_1 | ✅ | P4 | pipeline4:pool_c_bpc | 86943ms | 375 chars |
| 7 | wsj_2 | ✅ | P4 | pipeline4:pool_c_bpc | 84206ms | 532 chars |
| 8 | qq_finance_1 | ✅ | P4 | pipeline4:pool_c_bpc | 24032ms | 276 chars |
| 9 | qq_finance_2 | ✅ | P4 | pipeline4:pool_c_bpc | 13542ms | 361 chars |
| 10 | marketwatch_1 | ✅ | P4 | pipeline4:pool_c_bpc | 96511ms | 619 chars |
| 11 | marketwatch_2 | ❌ | - | - | 110231ms | - |
| 12 | marketwatch_3 | ❌ | - | blocked:failed_site | 0ms | - |
| 13 | marketwatch_4 | ❌ | - | blocked:failed_site | 0ms | - |
| 14 | marketwatch_5 | ❌ | - | blocked:failed_site | 0ms | - |
| 15 | marketwatch_6 | ❌ | - | blocked:failed_site | 0ms | - |
| 16 | tradingview_1 | ✅ | P4 | pipeline4:pool_c_bpc | 79764ms | 371 chars |
| 17 | tradingview_2 | ✅ | P4 | pipeline4:pool_c_bpc | 74905ms | 256 chars |
| 18 | cnbc | ✅ | P4 | pipeline4:pool_c_bpc | 40712ms | 10088 chars |
| 19 | stcn_1 | ✅ | P4 | pipeline4:pool_c_bpc | 41833ms | 991 chars |
| 20 | stcn_2 | ✅ | P4 | pipeline4:pool_c_bpc | 10970ms | 2025 chars |
| 21 | wallstreetcn_1 | ✅ | P1 | pipeline1:scrapling_fetch | 251ms | 991 chars |
| 22 | wallstreetcn_2 | ✅ | P1 | pipeline1:scrapling_fetch | 256ms | 981 chars |
| 23 | eeo_1 | ✅ | P4 | pipeline4:pool_c_bpc | 38781ms | 287 chars |
| 24 | eeo_2 | ✅ | P4 | pipeline4:pool_c_bpc | 36223ms | 316 chars |
| 25 | yicai_21 | ✅ | P1 | pipeline1:scrapling_fetch | 185ms | 324 chars |
| 26 | ft_1 | ✅ | P4 | pipeline4:pool_c_bpc | 79827ms | 1093 chars |
| 27 | ft_2 | ✅ | P4 | pipeline4:pool_c_bpc | 79512ms | 1056 chars |
| 28 | ft_3 | ✅ | P4 | pipeline4:pool_c_bpc | 82141ms | 1090 chars |
| 29 | cs | ❌ | - | - | 19567ms | - |
| 30 | bjnews | ✅ | P4 | pipeline4:pool_c_bpc | 11027ms | 651 chars |
| 31 | jiemian | ✅ | P4 | pipeline4:pool_c_bpc | 12150ms | 290 chars |
| 32 | cls | ✅ | P1 | pipeline1:scrapling_fetch | 793ms | 410 chars |

## Failed URLs Analysis

### marketwatch_2
- **URL:** https://r.jina.ai/http://https://www.marketwatch.com/story/the-world-cup-could-deliver-fox-a-ratings-bonanza-there-will-be-all-sorts-of-viewership-records-950604d3?mod=mw_rss_topstories
- **Error:** All 5 pipelines failed: Pipeline 1 exception: Failed to perform, curl: (28) Failed to connect to r.jina.ai port 443 after 21050 ms: Could not connect to server. See https://curl.se/libcurl/c/libcurl-errors.html first for more details.; Pipeline 2: captcha/403/access denied; Pipeline 3: still blocked by WAF; Pipeline 4: ins
- **Method:** 

### marketwatch_3
- **URL:** https://r.jina.ai/http://https://www.marketwatch.com/story/rip-euro-summer-americans-are-trading-tuscany-for-tacoma-thanks-to-soaring-airfares-44751904?mod=mw_rss_topstories
- **Error:** Site temporarily unscrapable: Pipeline 1 exception: Failed to perform, curl: (28) Failed to connect to r.jina.ai port 443 after 21050 ms: Could not connect to server. See https://curl.se/libcurl/c/libcurl-errors.html first for more details.; Pipeline 2: captcha/403/access denied; Pipeline 3: still blocked by WAF; Pipeline 4: insufficient content after BPC; Pipeline 5: all bypass methods failed
- **Method:** blocked:failed_site

### marketwatch_4
- **URL:** https://r.jina.ai/http://https://www.marketwatch.com/story/spacex-employees-now-have-enough-wealth-on-paper-to-buy-every-home-in-this-texas-city-ce0842be?mod=mw_rss_topstories
- **Error:** Site temporarily unscrapable: Pipeline 1 exception: Failed to perform, curl: (28) Failed to connect to r.jina.ai port 443 after 21050 ms: Could not connect to server. See https://curl.se/libcurl/c/libcurl-errors.html first for more details.; Pipeline 2: captcha/403/access denied; Pipeline 3: still blocked by WAF; Pipeline 4: insufficient content after BPC; Pipeline 5: all bypass methods failed
- **Method:** blocked:failed_site

### marketwatch_5
- **URL:** https://r.jina.ai/http://https://www.marketwatch.com/story/the-rich-keep-spending-money-on-unapologetic-luxury-and-its-raising-prices-on-everyday-goods-for-everyone-cdc4546b?mod=mw_rss_topstories
- **Error:** Site temporarily unscrapable: Pipeline 1 exception: Failed to perform, curl: (28) Failed to connect to r.jina.ai port 443 after 21050 ms: Could not connect to server. See https://curl.se/libcurl/c/libcurl-errors.html first for more details.; Pipeline 2: captcha/403/access denied; Pipeline 3: still blocked by WAF; Pipeline 4: insufficient content after BPC; Pipeline 5: all bypass methods failed
- **Method:** blocked:failed_site

### marketwatch_6
- **URL:** https://r.jina.ai/http://https://www.marketwatch.com/story/defaults-in-debt-markets-are-starting-again-warns-pimco-heres-the-bond-giants-game-plan-16559c6d?mod=mw_rss_topstories
- **Error:** Site temporarily unscrapable: Pipeline 1 exception: Failed to perform, curl: (28) Failed to connect to r.jina.ai port 443 after 21050 ms: Could not connect to server. See https://curl.se/libcurl/c/libcurl-errors.html first for more details.; Pipeline 2: captcha/403/access denied; Pipeline 3: still blocked by WAF; Pipeline 4: insufficient content after BPC; Pipeline 5: all bypass methods failed
- **Method:** blocked:failed_site

### cs
- **URL:** https://jnzstatic.cs.com.cn/zzb/htmlInfo/03bc5854363a4c609195f01c661365c0.html
- **Error:** All 5 pipelines failed: Pipeline 1: blocked/empty/redirect to captcha; Pipeline 2: captcha/403/access denied; Pipeline 3: still blocked by WAF; Pipeline 4: insufficient content after BPC; Pipeline 5: all bypass methods failed
- **Method:** 

