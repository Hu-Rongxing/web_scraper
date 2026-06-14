# 智能体使用规范 — article_reader

**所有智能体在使用 article_reader 抓取新闻时，必须严格遵守以下规则。**

---

## 核心原则

### 1. 优先使用原网站，RSS 仅作备选

**除非 RSS 通过同步验证，否则必须直接抓取原网站。**

RSS 验证标准：
- **同步延迟** ≤ 30 秒
- **文章匹配率** ≥ 90%
- **数量匹配率** ≥ 90%（允许 ±10% 误差）

**验证方法**：
```python
from article_reader import RSSValidator, ArticleInfo

validator = RSSValidator()
result = await validator.validate(
    rss_url="https://example.com/rss",
    original_url="https://example.com",
    rss_articles=rss_articles,
    original_articles=original_articles,
)

if not result.is_valid:
    # 必须使用原网站 URL，不得使用 RSS
    url = original_url
```

### 2. 不得跳过反封锁突破

**管线 1-4 失败后，必须尝试管线 5 反封锁突破，不得直接放弃。**

管线 5 会自动尝试 12+ 种突破策略：
- Archive.org / Google Cache / archive.today
- 12ft.io / removepaywall.com / freedium.cfd
- Reader Mode / AMP / 打印版
- 社交媒体 Referer / Bot User-Agent
- Cookie 操纵 / 禁用 JS

**示例**：
```python
from article_reader import SmartFetcher

async with SmartFetcher() as fetcher:
    # 自动降级：管线 1→2→3→4→5
    result = await fetcher.fetch("https://www.wsj.com/articles/...")
    
    if result.success:
        # 记录突破方式
        bypass_method = result.meta.get("bypass_method")
        if bypass_method:
            logger.info(f"突破成功: {bypass_method}")
```

### 3. 记录突破方式

**成功突破时，必须记录使用的突破方式到日志。**

突破方式包括：
- `archive_org` - Wayback Machine
- `google_cache` - Google 缓存
- `archive_today` - archive.ph
- `12ft_io` - 12ft.io 付费墙绕过
- `removepaywall` - removepaywall.com
- `freedium` - Medium 付费墙绕过
- `reader_mode` - Reader Mode
- `amp_version` - AMP 版本
- `print_version` - 打印版本
- `referer_social` - 社交媒体 Referer
- `bot_user_agent` - 搜索引擎爬虫 UA
- `cookie_manipulation` - Cookie 操纵

### 4. RSS 验证失败处理

**RSS 验证失败时，必须使用原网站 URL 抓取，不得降级到 RSS。**

常见失败原因：
- 延迟 > 30 秒（RSS 更新频率低）
- 文章遗漏（RSS 只包含部分内容）
- 标题不匹配（RSS 标题被截断或修改）
- 数量差异大（RSS 只包含最新文章）

### 5. 不得提前放弃

**遇到反爬/付费墙时，必须尝试所有管线，不得提前放弃。**

完整降级链：
```
管线 1: HTTP 轻量（curl_cffi）
  ↓ 失败
管线 2: 基础渲染（Pool A CloakBrowser）
  ↓ 失败
管线 3: 高防护（Pool B + humanize）
  ↓ 失败
管线 4: 付费墙绕过（Pool C + BPC 扩展）
  ↓ 失败
管线 5: 反封锁突破（12+ 种策略）
  ↓ 失败
管线 6: nodriver 兜底（正版 Chrome）
```

---

## 常见场景处理

### 场景 1: WSJ / NYTimes / The Economist 等付费墙站点

```python
# 正确做法
async with SmartFetcher() as fetcher:
    result = await fetcher.fetch("https://www.wsj.com/articles/...")
    # 自动尝试管线 1→2→3→4→5，管线 5 会尝试 archive.org、12ft.io 等

# 错误做法
# ✗ 直接放弃，不尝试管线 5
# ✗ 使用未验证的 RSS 源
```

### 场景 2: 新闻站点有 RSS 源

```python
# 正确做法
validator = RSSValidator()
result = await validator.validate(rss_url, original_url, rss_articles, original_articles)

if result.is_valid:
    # 可以使用 RSS
    articles = rss_articles
else:
    # 必须抓取原网站
    articles = await fetcher.fetch(original_url)

# 错误做法
# ✗ 不验证 RSS 同步性，直接使用
# ✗ RSS 验证失败后仍然使用 RSS
```

### 场景 3: 遇到 Cloudflare / DataDome 反爬

```python
# 正确做法
async with SmartFetcher() as fetcher:
    result = await fetcher.fetch("https://example.com/article")
    # 管线 3 会自动启用 humanize 拟人模拟
    # 管线 5 会尝试 archive.org、Google Cache 等

# 错误做法
# ✗ 遇到 403 就放弃
# ✗ 不尝试管线 5 的反封锁突破
```

---

## 日志记录要求

**必须记录以下信息**：

1. **抓取结果**
   ```python
   logger.info(f"抓取成功: {url}, 管线: P{result.pipeline_level}, 方法: {result.method}")
   ```

2. **突破方式**
   ```python
   if result.meta.get("bypass_method"):
       logger.info(f"突破成功: {result.meta['bypass_method']}")
   ```

3. **RSS 验证**
   ```python
   logger.info(f"RSS 验证: {rss_url}, 结果: {'通过' if result.is_valid else '失败'}")
   if not result.is_valid:
       logger.warning(f"RSS 验证失败: {result.reason}")
   ```

4. **失败原因**
   ```python
   if not result.success:
       logger.error(f"抓取失败: {url}, 错误: {result.error}")
   ```

---

## 禁止行为

**以下行为严格禁止**：

1. ❌ **跳过反封锁突破**：管线 1-4 失败后直接放弃，不尝试管线 5
2. ❌ **使用未验证的 RSS**：不验证同步性就使用 RSS 替代原网站
3. ❌ **RSS 验证失败后仍使用**：验证失败后仍然使用 RSS
4. ❌ **提前放弃**：遇到反爬/付费墙就放弃，不尝试所有管线
5. ❌ **不记录突破方式**：成功突破后不记录使用的突破方式
6. ❌ **不记录失败原因**：抓取失败后不记录失败原因

---

## 检查清单

**每次抓取前，确认以下事项**：

- [ ] 是否优先使用原网站？
- [ ] 如果使用 RSS，是否已验证同步性？
- [ ] 是否准备好尝试所有管线（1-6）？
- [ ] 是否准备好记录突破方式？
- [ ] 是否准备好记录失败原因？

**每次抓取后，确认以下事项**：

- [ ] 是否记录了抓取结果（成功/失败）？
- [ ] 如果成功突破，是否记录了突破方式？
- [ ] 如果失败，是否记录了失败原因？
- [ ] 如果使用 RSS，是否记录了验证结果？

---

## 联系方式

**如有问题，请联系**：
- 项目维护者：小龙虾（main agent）
- 项目路径：`D:\oc_workspace\main\article_reader`
- 文档路径：`D:\oc_workspace\main\article_reader\README.md`

---

**最后更新**：2026-06-14
**版本**：v3.1.0
