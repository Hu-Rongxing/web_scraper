# 重要规则 — 所有智能体必读

**本文档包含 article_reader 项目的核心规则，所有使用本项目的智能体必须遵守。**

---

## 规则 1: RSS 同步验证（强制执行）

### 要求
使用 RSS 替代原网站抓取时，**必须**通过同步验证：

- **同步延迟** ≤ 30 秒
- **文章匹配率** ≥ 90%
- **数量匹配率** ≥ 90%

### 验证方法
```python
from article_reader import RSSValidator

validator = RSSValidator()
result = await validator.validate(rss_url, original_url, rss_articles, original_articles)

if not result.is_valid:
    # 必须使用原网站 URL，不得使用 RSS
    raise ValueError(f"RSS 验证失败: {result.reason}")
```

### 违规后果
- ❌ 使用未验证的 RSS 源
- ❌ RSS 验证失败后仍使用 RSS
- ✅ 必须直接抓取原网站

---

## 规则 2: 反封锁突破（强制执行）

### 要求
管线 1-4 失败后，**必须**尝试管线 5 反封锁突破，**不得直接放弃**。

### 管线 5 自动尝试的策略
1. Archive.org (Wayback Machine)
2. Google Cache
3. archive.today (archive.ph)
4. 12ft.io (付费墙绕过)
5. removepaywall.com
6. freedium.cfd (Medium 专用)
7. Reader Mode / AMP / 打印版
8. 社交媒体 Referer 伪装
9. 搜索引擎爬虫 User-Agent
10. Cookie 操纵
11. 禁用 JavaScript
12. RSS 全文获取

### 违规后果
- ❌ 遇到反爬/付费墙就放弃
- ❌ 跳过管线 5 直接标记失败
- ✅ 必须尝试所有管线（1-6）

---

## 规则 3: 日志记录（强制执行）

### 必须记录的信息

#### 1. 抓取结果
```python
logger.info(f"抓取成功: {url}, 管线: P{result.pipeline_level}, 方法: {result.method}")
```

#### 2. 突破方式
```python
if result.meta.get("bypass_method"):
    logger.info(f"突破成功: {result.meta['bypass_method']}")
```

#### 3. RSS 验证
```python
logger.info(f"RSS 验证: {rss_url}, 结果: {'通过' if result.is_valid else '失败'}")
```

#### 4. 失败原因
```python
if not result.success:
    logger.error(f"抓取失败: {url}, 错误: {result.error}")
```

---

## 规则 4: 优先级（强制执行）

### 抓取优先级
1. **优先使用原网站**（除非 RSS 通过验证）
2. **优先尝试低级管线**（管线 1 → 2 → 3 → 4 → 5 → 6）
3. **优先记录详细信息**（突破方式、失败原因）

### RSS 使用条件
- ✅ RSS 通过同步验证
- ✅ 延迟 ≤ 30 秒
- ✅ 匹配率 ≥ 90%
- ✅ 数量匹配率 ≥ 90%

---

## 禁止行为清单

以下行为**严格禁止**：

1. ❌ **跳过反封锁突破**
   - 管线 1-4 失败后直接放弃
   - 不尝试管线 5 的反封锁策略

2. ❌ **使用未验证的 RSS**
   - 不验证同步性就使用 RSS
   - 假设 RSS 总是同步的

3. ❌ **RSS 验证失败后仍使用**
   - 验证失败后仍然使用 RSS
   - 忽略验证结果

4. ❌ **提前放弃**
   - 遇到 403/反爬就放弃
   - 不尝试所有管线

5. ❌ **不记录突破方式**
   - 成功突破后不记录使用的突破方式
   - 无法追踪哪些策略有效

6. ❌ **不记录失败原因**
   - 抓取失败后不记录失败原因
   - 无法诊断问题

---

## 检查清单

### 抓取前
- [ ] 是否优先使用原网站？
- [ ] 如果使用 RSS，是否已验证同步性？
- [ ] 是否准备好尝试所有管线（1-6）？
- [ ] 是否准备好记录突破方式？

### 抓取后
- [ ] 是否记录了抓取结果（成功/失败）？
- [ ] 如果成功突破，是否记录了突破方式？
- [ ] 如果失败，是否记录了失败原因？
- [ ] 如果使用 RSS，是否记录了验证结果？

---

## 文档位置

### 核心文档
- **README.md**: 项目完整文档
- **AGENT_GUIDELINES.md**: 智能体使用规范（详细版）
- **IMPORTANT_RULES.md**: 本文档（核心规则摘要）

### 代码位置
- **pipelines/anti_block.py**: 反封锁突破模块
- **pipelines/rss_validator.py**: RSS 同步验证模块
- **pipelines/pipeline.py**: 管线管理器（包含管线 5）

### 测试位置
- **test/test_bypass.py**: 反封锁突破测试

---

## 违规处理

**首次违规**：
- 记录违规行为
- 要求立即改正
- 重新学习规则

**重复违规**：
- 暂停使用 article_reader
- 强制重新学习规则
- 需要人工审核后才能恢复

---

## 联系方式

**如有问题，请联系**：
- 项目维护者：小龙虾（main agent）
- 项目路径：`D:\oc_workspace\main\article_reader`
- 文档路径：`D:\oc_workspace\main\article_reader\README.md`

---

**最后更新**：2026-06-14  
**版本**：v3.1.0  
**状态**：✅ 强制执行

---

## 附录：快速参考

### RSS 验证快速代码
```python
from article_reader import RSSValidator, ArticleInfo

validator = RSSValidator()
result = await validator.validate(rss_url, original_url, rss_articles, original_articles)

if result.is_valid:
    # 可以使用 RSS
    pass
else:
    # 必须使用原网站
    raise ValueError(f"RSS 验证失败: {result.reason}")
```

### 反封锁突破快速代码
```python
from article_reader import SmartFetcher

async with SmartFetcher() as fetcher:
    # 自动尝试管线 1→2→3→4→5
    result = await fetcher.fetch(url)
    
    if result.success:
        # 记录突破方式
        if result.meta.get("bypass_method"):
            logger.info(f"突破成功: {result.meta['bypass_method']}")
    else:
        # 记录失败原因
        logger.error(f"抓取失败: {url}, 错误: {result.error}")
```

### 完整降级链
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

**所有智能体必须遵守以上规则，违者将受到处理。**
