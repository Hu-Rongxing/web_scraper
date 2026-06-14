# Agent Guidelines — article_reader

**所有使用 article_reader 抓取新闻的智能体必须严格遵守。**

---

## 核心规则

### 1. 优先原网站，RSS 仅验证后使用

RSS 必须通过 `RSSValidator` 验证后才可使用：

- 同步延迟 ≤ 30s
- 文章匹配率 ≥ 90%
- 数量匹配率 ≥ 90%

```python
from article_reader import RSSValidator

validator = RSSValidator()
result = await validator.validate(rss_url, original_url, rss_articles, original_articles)

if not result.is_valid:
    # 验证失败 → 必须使用原网站 URL
    url = original_url
```

### 2. 必须走完五级管线，不得提前放弃

```
管线 1: HTTP 轻量（curl_cffi / Scrapling Fetcher）
  ↓ 失败
管线 2: 基础渲染（Pool A CloakBrowser）
  ↓ 失败
管线 3: 高防护（Pool B + humanize + 持久化 Profile）
  ↓ 失败
管线 4: 付费墙绕过（Pool C + BPC 扩展，用完即毁）
  ↓ 失败
管线 5: 反封锁突破（12+ 种策略）
```

管线 5 自动尝试的策略：
1. archive.org (Wayback Machine)
2. Google Cache
3. archive.today (archive.ph)
4. 12ft.io / removepaywall.com / freedium.cfd
5. Reader Mode / AMP / 打印版
6. 社交媒体 Referer 伪装
7. 搜索引擎爬虫 User-Agent
8. Cookie 操纵 / 禁用 JavaScript

### 3. 必须记录日志

```python
# 抓取结果
logger.info(f"抓取: {url}, 管线: P{result.pipeline_level}, 方法: {result.method}")

# 突破方式
if result.meta.get("bypass_method"):
    logger.info(f"突破: {result.meta['bypass_method']}")

# RSS 验证
logger.info(f"RSS 验证: {rss_url}, {'通过' if result.is_valid else '失败'}")
if not result.is_valid:
    logger.warning(f"原因: {result.reason}")

# 失败原因
if not result.success:
    logger.error(f"失败: {url}, 错误: {result.error}")
```

---

## 使用示例

### 正常抓取（自动降级）

```python
from article_reader import SmartFetcher

async with SmartFetcher() as fetcher:
    result = await fetcher.fetch("https://www.wsj.com/articles/...")
    # 自动：管线 1→2→3→4→5

    if result.success:
        logger.info(f"管线: P{result.pipeline_level}, 内容: {result.length} chars")
        bypass = result.meta.get("bypass_method")
        if bypass:
            logger.info(f"突破方式: {bypass}")
    else:
        logger.error(f"失败: {result.error}")
```

### RSS 验证后使用

```python
from article_reader import RSSValidator

validator = RSSValidator()
result = await validator.validate(rss_url, original_url, rss_articles, original_articles)

if result.is_valid:
    articles = rss_articles   # 可以使用 RSS
else:
    articles = await fetcher.fetch(original_url)  # 必须抓原网站
```

---

## 禁止行为

| # | 行为 | 说明 |
|---|------|------|
| ❌ | 跳过管线 5 | 管线 1-4 失败后不得直接放弃 |
| ❌ | 未验证 RSS | 不得使用未经验证的 RSS 源 |
| ❌ | 验证失败仍用 RSS | RSS 验证失败后不得继续使用 |
| ❌ | 提前放弃 | 遇到 403/CAPTCHA 就放弃 |
| ❌ | 不记录日志 | 突破方式、失败原因必须记录 |

---

## 检查清单

**抓取前**：
- [ ] 优先使用原网站？
- [ ] RSS 已验证（如使用）？
- [ ] 准备好尝试全部管线？

**抓取后**：
- [ ] 记录了抓取结果？
- [ ] 记录了突破方式（如有）？
- [ ] 记录了失败原因（如有）？

---

## 关键依赖

| 包 | 用途 | 官方文档 |
|---|------|----------|
| **curl_cffi** | P1 HTTP 模拟浏览器指纹 | https://github.com/lexiforest/curl_cffi |
| **Scrapling** | P1 Fetcher + DOM 解析 | https://scrapling.readthedocs.io/en/latest/ |
| **CloakBrowser** | P2/P3/P4 反检测浏览器 | https://cloakbrowser.dev/ |
| **Bypass Paywalls Clean** | P4 付费墙绕过扩展 | https://gitflic.ru/project/magnolia1234/bypass-paywalls-chrome-clean |
| **trafilatura** | 内容提取 | https://trafilatura.readthedocs.io/ |
| **nodriver** | 管线 6 兜底（正版 Chrome） | https://ultrafunkamsterdam.github.io/nodriver/ |

---

**版本**: v3.1 · **维护者**: 小龙虾 · **路径**: `D:\oc_workspace\main\article_reader`
