# -*- coding: utf-8 -*-
"""
pipelines/rss_validator.py — RSS 同步验证器

验证 RSS 源与原网站的同步性，确保 RSS 可以替代原网站抓取。

规则：
1. RSS 文章发布时间与原网站发布时间差 ≤ 30 秒
2. RSS 文章数量与原网站文章数量一致（允许 ±10% 误差）
3. RSS 文章标题/URL 与原网站匹配度 ≥ 90%

不满足以上条件的 RSS 源不得使用，必须直接抓取原网站。
"""

import time
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional
from urllib.parse import urlparse

from ..config import logger


@dataclass
class RSSValidationResult:
    """RSS 验证结果"""
    rss_url: str
    original_url: str
    is_valid: bool
    sync_delay_seconds: float = 0.0  # 同步延迟（秒）
    article_match_ratio: float = 0.0  # 文章匹配率
    count_match_ratio: float = 0.0  # 数量匹配率
    reason: str = ""


@dataclass
class ArticleInfo:
    """文章信息"""
    title: str
    url: str
    published_at: Optional[datetime] = None


class RSSValidator:
    """RSS 同步验证器"""
    
    # 验证阈值
    MAX_SYNC_DELAY_SECONDS = 30  # 最大同步延迟 30 秒
    MIN_ARTICLE_MATCH_RATIO = 0.9  # 最小文章匹配率 90%
    MIN_COUNT_MATCH_RATIO = 0.9  # 最小数量匹配率 90%（允许 ±10% 误差）
    
    def __init__(self, http_client=None):
        self._http = http_client
    
    async def validate(
        self,
        rss_url: str,
        original_url: str,
        rss_articles: List[ArticleInfo],
        original_articles: List[ArticleInfo],
    ) -> RSSValidationResult:
        """
        验证 RSS 源是否可以替代原网站
        
        Args:
            rss_url: RSS 源 URL
            original_url: 原网站 URL
            rss_articles: RSS 文章列表
            original_articles: 原网站文章列表
        
        Returns:
            RSSValidationResult
        """
        logger.info(f"Validating RSS sync: {rss_url} vs {original_url}")
        
        # 1. 检查文章数量匹配率
        count_ratio = self._check_count_match(rss_articles, original_articles)
        
        # 2. 检查文章匹配率（标题/URL）
        article_ratio = self._check_article_match(rss_articles, original_articles)
        
        # 3. 检查同步延迟
        sync_delay = self._check_sync_delay(rss_articles, original_articles)
        
        # 4. 综合判断
        is_valid = (
            sync_delay <= self.MAX_SYNC_DELAY_SECONDS and
            article_ratio >= self.MIN_ARTICLE_MATCH_RATIO and
            count_ratio >= self.MIN_COUNT_MATCH_RATIO
        )
        
        reason = ""
        if not is_valid:
            reasons = []
            if sync_delay > self.MAX_SYNC_DELAY_SECONDS:
                reasons.append(f"sync delay {sync_delay:.1f}s > {self.MAX_SYNC_DELAY_SECONDS}s")
            if article_ratio < self.MIN_ARTICLE_MATCH_RATIO:
                reasons.append(f"article match {article_ratio:.1%} < {self.MIN_ARTICLE_MATCH_RATIO:.1%}")
            if count_ratio < self.MIN_COUNT_MATCH_RATIO:
                reasons.append(f"count match {count_ratio:.1%} < {self.MIN_COUNT_MATCH_RATIO:.1%}")
            reason = "; ".join(reasons)
        
        result = RSSValidationResult(
            rss_url=rss_url,
            original_url=original_url,
            is_valid=is_valid,
            sync_delay_seconds=sync_delay,
            article_match_ratio=article_ratio,
            count_match_ratio=count_ratio,
            reason=reason,
        )
        
        if is_valid:
            logger.info(f"RSS validation PASSED: {rss_url} (delay={sync_delay:.1f}s, match={article_ratio:.1%})")
        else:
            logger.warning(f"RSS validation FAILED: {rss_url} - {reason}")
        
        return result
    
    def _check_count_match(
        self,
        rss_articles: List[ArticleInfo],
        original_articles: List[ArticleInfo],
    ) -> float:
        """检查文章数量匹配率"""
        if not original_articles:
            return 1.0 if not rss_articles else 0.0
        
        rss_count = len(rss_articles)
        original_count = len(original_articles)
        
        # 计算匹配率（允许 ±10% 误差）
        ratio = min(rss_count, original_count) / max(rss_count, original_count)
        return ratio
    
    def _check_article_match(
        self,
        rss_articles: List[ArticleInfo],
        original_articles: List[ArticleInfo],
    ) -> float:
        """检查文章匹配率（标题/URL）"""
        if not original_articles:
            return 1.0 if not rss_articles else 0.0
        
        matched = 0
        for orig in original_articles:
            for rss in rss_articles:
                if self._articles_match(orig, rss):
                    matched += 1
                    break
        
        return matched / len(original_articles)
    
    def _articles_match(self, a: ArticleInfo, b: ArticleInfo) -> bool:
        """判断两篇文章是否匹配"""
        # URL 匹配（忽略查询参数和锚点）
        url_a = self._normalize_url(a.url)
        url_b = self._normalize_url(b.url)
        if url_a == url_b:
            return True
        
        # 标题匹配（去除空白和标点）
        title_a = self._normalize_title(a.title)
        title_b = self._normalize_title(b.title)
        if title_a and title_b and title_a == title_b:
            return True
        
        # 标题相似度（简单字符匹配）
        if title_a and title_b:
            similarity = self._string_similarity(title_a, title_b)
            if similarity >= 0.8:
                return True
        
        return False
    
    def _check_sync_delay(
        self,
        rss_articles: List[ArticleInfo],
        original_articles: List[ArticleInfo],
    ) -> float:
        """检查同步延迟（秒）"""
        if not rss_articles or not original_articles:
            return 0.0
        
        delays = []
        for rss in rss_articles:
            if not rss.published_at:
                continue
            for orig in original_articles:
                if orig.published_at and self._articles_match(rss, orig):
                    delay = abs((rss.published_at - orig.published_at).total_seconds())
                    delays.append(delay)
                    break
        
        if not delays:
            return 0.0
        
        # 返回平均延迟
        return sum(delays) / len(delays)
    
    @staticmethod
    def _normalize_url(url: str) -> str:
        """标准化 URL（去除查询参数和锚点）"""
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    
    @staticmethod
    def _normalize_title(title: str) -> str:
        """标准化标题（去除空白和标点）"""
        import re
        title = re.sub(r'\s+', ' ', title.strip())
        title = re.sub(r'[^\w\s]', '', title)  # 去除标点
        return title.lower()
    
    @staticmethod
    def _string_similarity(a: str, b: str) -> float:
        """计算字符串相似度（简单 Jaccard 相似度）"""
        set_a = set(a.lower().split())
        set_b = set(b.lower().split())
        if not set_a or not set_b:
            return 0.0
        intersection = set_a & set_b
        union = set_a | set_b
        return len(intersection) / len(union)


class RSSPolicy:
    """RSS 使用策略管理器"""
    
    def __init__(self):
        self._validator = RSSValidator()
        self._validated_cache: dict[str, RSSValidationResult] = {}
    
    async def should_use_rss(
        self,
        rss_url: str,
        original_url: str,
        rss_articles: List[ArticleInfo],
        original_articles: List[ArticleInfo],
    ) -> bool:
        """
        判断是否应该使用 RSS 替代原网站
        
        Returns:
            True 表示可以使用 RSS，False 表示必须抓取原网站
        """
        # 检查缓存
        cache_key = f"{rss_url}:{original_url}"
        if cache_key in self._validated_cache:
            result = self._validated_cache[cache_key]
            # 缓存有效期 1 小时
            if time.time() - time.time() < 3600:
                return result.is_valid
        
        # 验证 RSS
        result = await self._validator.validate(
            rss_url, original_url, rss_articles, original_articles
        )
        
        # 缓存结果
        self._validated_cache[cache_key] = result
        
        return result.is_valid
    
    def clear_cache(self):
        """清除验证缓存"""
        self._validated_cache.clear()
