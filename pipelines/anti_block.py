# -*- coding: utf-8 -*-
"""
pipelines/anti_block.py — 反封锁突破模块 v1.0

实现多种突破 ID 墙、登录墙、订阅墙、付费墙的技术：

1. Archive/Cache 服务
   - Wayback Machine (archive.org)
   - Google Cache
   - archive.today (archive.ph)
   
2. Reader Mode 绕过
   - Safari Reader View 格式 URL
   - Firefox Reader View 格式
   
3. Cookie/Session 操纵
   - 清除付费墙 Cookie
   - 模拟已登录状态
   - Incognito 模式特征
   
4. Referer 伪装
   - 从 Google/Facebook/Twitter 跳转
   - 社交媒体来源伪装
   
5. 付费墙绕过技术
   - 禁用 JavaScript (noscript 版本)
   - AMP 版本获取
   - 打印版本获取
   - RSS/Atom 全文获取
   
6. 内容墙检测与自动降级
   - 检测截断内容
   - 自动尝试多种突破方式
"""

import asyncio
import re
import time
from dataclasses import dataclass
from typing import Optional, Callable, Awaitable
from urllib.parse import urlparse, quote_plus

from ..config import logger


# ============================================================
# 突破方式枚举
# ============================================================

class BypassMethod:
    """突破方式"""
    DIRECT = "direct"                    # 直接访问（无突破）
    ARCHIVE_ORG = "archive_org"          # Wayback Machine
    ARCHIVE_TODAY = "archive_today"      # archive.ph
    GOOGLE_CACHE = "google_cache"        # Google 缓存
    READER_MODE = "reader_mode"          # 浏览器阅读模式
    REFERER_GOOGLE = "referer_google"    # Google 来源
    REFERER_SOCIAL = "referer_social"    # 社交媒体来源
    NO_JS = "no_js"                      # 禁用 JS
    AMP_VERSION = "amp_version"          # AMP 版本
    PRINT_VERSION = "print_version"      # 打印版本
    RSS_FULLTEXT = "rss_fulltext"        # RSS 全文
    COOKIE_BYPASS = "cookie_bypass"      # Cookie 操纵
    INCOGNITO = "incognito"              # 无痕模式特征


# ============================================================
# 突破结果
# ============================================================

@dataclass
class BypassResult:
    """突破尝试结果"""
    method: str
    success: bool
    html: str = ""
    content: str = ""
    title: str = ""
    error: str = ""
    elapsed_ms: float = 0
    content_length: int = 0
    is_truncated: bool = False  # 内容是否被截断


# ============================================================
# 付费墙/内容墙检测器
# ============================================================

class WallDetector:
    """检测各种类型的墙"""
    
    # 付费墙信号
    PAYWALL_SIGNALS = [
        # 英文
        "subscribe now", "subscription required", "already a subscriber",
        "create an account to continue", "log in to read",
        "you've reached your article limit", "metered paywall",
        "premium article", "member only content",
        "start your free trial", "unlock this article",
        # 中文
        "订阅后阅读全文", "登录后继续阅读", "付费阅读",
        "会员专享", "订阅解锁", "限时免费",
        "您已达到阅读上限", "注册以继续",
    ]
    
    # 付费墙 JS/CSS 特征
    PAYWALL_SCRIPT_PATTERNS = [
        r"piano\.io", r"tinypass\.com", r"evolok", r"poool",
        r"paywall\.js", r"subscription-wall", r"metered-paywall",
        r"article-count.*limit", r"views-remaining",
    ]
    
    # 内容截断信号
    TRUNCATION_SIGNALS = [
        "<!-- paywall -->", "<!-- truncated -->",
        "class=\"paywall\"", "id=\"paywall\"",
        "class=\"subscribe-wall\"", "id=\"subscription-prompt\"",
        "data-paywall", "data-subscription-required",
        "...continued", "read more to continue",
    ]
    
    # 登录墙信号
    LOGIN_WALL_SIGNALS = [
        "please log in", "sign in to continue", "login required",
        "register to read", "create account",
        "请登录", "注册后阅读", "登录后查看",
    ]
    
    @classmethod
    def detect_paywall(cls, html: str) -> bool:
        """检测是否存在付费墙"""
        html_lower = html.lower()
        
        # 检查文本信号
        for signal in cls.PAYWALL_SIGNALS:
            if signal.lower() in html_lower:
                return True
        
        # 检查 JS/CSS 特征
        for pattern in cls.PAYWALL_SCRIPT_PATTERNS:
            if re.search(pattern, html, re.I):
                return True
        
        return False
    
    @classmethod
    def detect_truncation(cls, html: str, content: str) -> bool:
        """检测内容是否被截断"""
        # 检查 HTML 中的截断信号
        for signal in cls.TRUNCATION_SIGNALS:
            if signal.lower() in html.lower():
                return True
        
        # 检查内容长度异常短（相对 HTML 大小）
        if len(html) > 50000 and len(content) < 500:
            return True
        
        # 检查内容是否突然中断（没有正常结尾）
        if content and not content.rstrip().endswith(('.', '。', '!', '！', '?', '？', '"', '"', '”')):
            # 内容不以句号等结尾，可能被截断
            if len(content) > 100:
                return True
        
        return False
    
    @classmethod
    def detect_login_wall(cls, html: str) -> bool:
        """检测是否存在登录墙"""
        html_lower = html.lower()
        for signal in cls.LOGIN_WALL_SIGNALS:
            if signal.lower() in html_lower:
                return True
        return False
    
    @classmethod
    def detect_wall_type(cls, html: str, content: str) -> Optional[str]:
        """检测墙的类型"""
        if cls.detect_paywall(html):
            return "paywall"
        if cls.detect_login_wall(html):
            return "login_wall"
        if cls.detect_truncation(html, content):
            return "truncated"
        return None


# ============================================================
# URL 转换器
# ============================================================

class URLTransformer:
    """将原始 URL 转换为各种替代版本"""
    
    @staticmethod
    def to_archive_org(url: str) -> str:
        """转换为 Wayback Machine URL"""
        return f"https://web.archive.org/web/2024/{url}"
    
    @staticmethod
    def to_archive_org_latest(url: str) -> str:
        """转换为 Wayback Machine 最新快照"""
        return f"https://web.archive.org/web/20240000000000*/{url}"
    
    @staticmethod
    def to_archive_today(url: str) -> str:
        """转换为 archive.today URL"""
        return f"https://archive.ph/newest/{url}"
    
    @staticmethod
    def to_google_cache(url: str) -> str:
        """转换为 Google Cache URL"""
        return f"https://webcache.googleusercontent.com/search?q=cache:{url}"
    
    @staticmethod
    def to_reader_mode(url: str) -> str:
        """转换为 Safari Reader View URL"""
        # Safari Reader View 格式
        return f"reader://reader/{url}"
    
    @staticmethod
    def to_firefox_reader(url: str) -> str:
        """转换为 Firefox Reader View URL"""
        return f"about:reader?url={quote_plus(url)}"
    
    @staticmethod
    def to_amp_version(url: str) -> str:
        """尝试转换为 AMP 版本"""
        parsed = urlparse(url)
        # 常见的 AMP 路径模式
        amp_patterns = [
            url + "/amp",
            url + "?amp=1",
            url.replace(f"{parsed.scheme}://", f"{parsed.scheme}://amp."),
            url.replace("/articles/", "/amp/articles/"),
            url.replace("/news/", "/amp/news/"),
        ]
        return amp_patterns  # 返回多个候选
    
    @staticmethod
    def to_print_version(url: str) -> str:
        """尝试转换为打印版本"""
        parsed = urlparse(url)
        # 常见的打印版本模式
        print_patterns = [
            url + "?print=1",
            url + "&print=1",
            url.replace("/article/", "/print/"),
            f"{parsed.scheme}://print.{parsed.netloc}{parsed.path}",
        ]
        return print_patterns
    
    @staticmethod
    def extract_domain(url: str) -> str:
        """提取域名"""
        return urlparse(url).netloc
    
    @staticmethod
    def is_news_site(url: str) -> bool:
        """判断是否是新闻站点"""
        domain = urlparse(url).netloc.lower()
        news_indicators = [
            "news", "times", "post", "journal", "herald",
            "telegraph", "guardian", "bbc", "cnn", "reuters",
            "bloomberg", "wsj", "ft", "economist",
        ]
        return any(ind in domain for ind in news_indicators)


# ============================================================
# 突破策略执行器
# ============================================================

class BypassExecutor:
    """执行各种突破策略"""
    
    def __init__(self, http_client=None, browser_pool=None):
        self._http = http_client
        self._browser = browser_pool
        self._wall_detector = WallDetector()
        self._url_transformer = URLTransformer()
    
    async def try_bypass(
        self,
        url: str,
        original_html: str = "",
        original_content: str = "",
        wall_type: Optional[str] = None,
    ) -> list[BypassResult]:
        """
        尝试多种突破方式
        
        Args:
            url: 原始 URL
            original_html: 原始页面 HTML（用于检测墙类型）
            original_content: 原始内容（用于检测截断）
            wall_type: 已知的墙类型
            
        Returns:
            按优先级排序的突破结果列表
        """
        results = []
        
        # 如果没有提供墙类型，自动检测
        if not wall_type and original_html:
            wall_type = self._wall_detector.detect_wall_type(original_html, original_content)
        
        logger.info(f"Attempting bypass for {url}, wall_type={wall_type}")
        
        # 根据墙类型选择突破策略
        if wall_type == "paywall":
            results = await self._bypass_paywall(url)
        elif wall_type == "login_wall":
            results = await self._bypass_login_wall(url)
        elif wall_type == "truncated":
            results = await self._bypass_truncation(url)
        else:
            # 通用突破尝试
            results = await self._bypass_generic(url)
        
        # 过滤成功的结果
        successful = [r for r in results if r.success and r.content_length > 200]
        
        if successful:
            logger.info(f"Bypass success: {len(successful)} methods worked for {url}")
        else:
            logger.warning(f"All bypass methods failed for {url}")
        
        return successful
    
    async def _bypass_paywall(self, url: str) -> list[BypassResult]:
        """付费墙突破策略 - 综合使用多种方法"""
        results = []
        
        # 1. 尝试 Archive.org（最可靠）
        results.append(await self._try_archive_org(url))
        
        # 2. 尝试 Archive.today
        results.append(await self._try_archive_today(url))
        
        # 3. 尝试 Google Cache
        results.append(await self._try_google_cache(url))
        
        # 4. 尝试 12ft.io（专门绕过付费墙）
        results.append(await AdvancedBypass.try_12ft_io(url, self._http))
        
        # 5. 尝试 removepaywall.com
        results.append(await AdvancedBypass.try_removepaywall(url, self._http))
        
        # 6. 尝试 AMP 版本
        results.extend(await self._try_amp_version(url))
        
        # 7. 尝试禁用 JS 版本
        results.append(await self._try_no_js(url))
        
        # 8. 尝试 Reader Mode API
        results.append(await AdvancedBypass.try_reader_mode_api(url, self._http))
        
        # 9. 尝试 Cookie 操纵
        results.append(await AdvancedBypass.try_cookie_manipulation(url, self._http))
        
        # 10. 尝试社交媒体 Referer
        results.append(await AdvancedBypass.try_social_media_referer(url, self._http))
        
        # 11. 尝试搜索引擎爬虫 User-Agent
        results.append(await AdvancedBypass.try_bot_user_agent(url, self._http))
        
        # 12. 尝试 Google Referer
        results.append(await self._try_referer_google(url))
        
        return results
    
    async def _bypass_login_wall(self, url: str) -> list[BypassResult]:
        """登录墙突破策略 - 优先使用缓存和快照"""
        results = []
        
        # 1. Archive 服务（最可靠）
        results.append(await self._try_archive_org(url))
        results.append(await self._try_archive_today(url))
        
        # 2. Google Cache
        results.append(await self._try_google_cache(url))
        
        # 3. 12ft.io
        results.append(await AdvancedBypass.try_12ft_io(url, self._http))
        
        # 4. removepaywall.com
        results.append(await AdvancedBypass.try_removepaywall(url, self._http))
        
        # 5. RSS 全文（如果可用）
        results.append(await self._try_rss_fulltext(url))
        
        # 6. 搜索引擎爬虫 User-Agent
        results.append(await AdvancedBypass.try_bot_user_agent(url, self._http))
        
        # 7. 社交媒体 Referer
        results.append(await AdvancedBypass.try_social_media_referer(url, self._http))
        
        return results
    
    async def _bypass_truncation(self, url: str) -> list[BypassResult]:
        """内容截断突破策略 - 获取完整内容"""
        results = []
        
        # 1. Archive 完整版本
        results.append(await self._try_archive_org(url))
        results.append(await self._try_archive_today(url))
        
        # 2. Google Cache
        results.append(await self._try_google_cache(url))
        
        # 3. 打印版本（通常包含完整内容）
        results.extend(await self._try_print_version(url))
        
        # 4. AMP 版本
        results.extend(await self._try_amp_version(url))
        
        # 5. Reader Mode API
        results.append(await AdvancedBypass.try_reader_mode_api(url, self._http))
        
        # 6. 12ft.io
        results.append(await AdvancedBypass.try_12ft_io(url, self._http))
        
        return results
    
    async def _bypass_generic(self, url: str) -> list[BypassResult]:
        """通用突破策略 - 综合尝试所有方法"""
        results = []
        
        # 1. Archive 服务
        results.append(await self._try_archive_org(url))
        results.append(await self._try_archive_today(url))
        
        # 2. Google Cache
        results.append(await self._try_google_cache(url))
        
        # 3. 第三方绕过服务
        results.append(await AdvancedBypass.try_12ft_io(url, self._http))
        results.append(await AdvancedBypass.try_removepaywall(url, self._http))
        
        # 4. Reader Mode
        results.append(await AdvancedBypass.try_reader_mode_api(url, self._http))
        
        # 5. Referer 伪装
        results.append(await self._try_referer_google(url))
        results.append(await AdvancedBypass.try_social_media_referer(url, self._http))
        
        # 6. Bot User-Agent
        results.append(await AdvancedBypass.try_bot_user_agent(url, self._http))
        
        return results
    
    # ============================================================
    # 具体突破方法实现
    # ============================================================
    
    async def _try_archive_org(self, url: str) -> BypassResult:
        """尝试 Wayback Machine"""
        t0 = time.monotonic()
        try:
            archive_url = self._url_transformer.to_archive_org(url)
            # 使用 HTTP 客户端获取
            if self._http:
                html = await self._http.fetch(archive_url)
                if html and len(html) > 1000:
                    return BypassResult(
                        method=BypassMethod.ARCHIVE_ORG,
                        success=True,
                        html=html,
                        content_length=len(html),
                        elapsed_ms=(time.monotonic() - t0) * 1000,
                    )
            return BypassResult(
                method=BypassMethod.ARCHIVE_ORG,
                success=False,
                error="No content from archive.org",
                elapsed_ms=(time.monotonic() - t0) * 1000,
            )
        except Exception as e:
            return BypassResult(
                method=BypassMethod.ARCHIVE_ORG,
                success=False,
                error=str(e)[:200],
                elapsed_ms=(time.monotonic() - t0) * 1000,
            )
    
    async def _try_archive_today(self, url: str) -> BypassResult:
        """尝试 archive.today"""
        t0 = time.monotonic()
        try:
            archive_url = self._url_transformer.to_archive_today(url)
            if self._http:
                html = await self._http.fetch(archive_url)
                if html and len(html) > 1000:
                    return BypassResult(
                        method=BypassMethod.ARCHIVE_TODAY,
                        success=True,
                        html=html,
                        content_length=len(html),
                        elapsed_ms=(time.monotonic() - t0) * 1000,
                    )
            return BypassResult(
                method=BypassMethod.ARCHIVE_TODAY,
                success=False,
                error="No content from archive.today",
                elapsed_ms=(time.monotonic() - t0) * 1000,
            )
        except Exception as e:
            return BypassResult(
                method=BypassMethod.ARCHIVE_TODAY,
                success=False,
                error=str(e)[:200],
                elapsed_ms=(time.monotonic() - t0) * 1000,
            )
    
    async def _try_google_cache(self, url: str) -> BypassResult:
        """尝试 Google Cache"""
        t0 = time.monotonic()
        try:
            cache_url = self._url_transformer.to_google_cache(url)
            if self._http:
                html = await self._http.fetch(cache_url)
                if html and len(html) > 1000:
                    return BypassResult(
                        method=BypassMethod.GOOGLE_CACHE,
                        success=True,
                        html=html,
                        content_length=len(html),
                        elapsed_ms=(time.monotonic() - t0) * 1000,
                    )
            return BypassResult(
                method=BypassMethod.GOOGLE_CACHE,
                success=False,
                error="No content from Google Cache",
                elapsed_ms=(time.monotonic() - t0) * 1000,
            )
        except Exception as e:
            return BypassResult(
                method=BypassMethod.GOOGLE_CACHE,
                success=False,
                error=str(e)[:200],
                elapsed_ms=(time.monotonic() - t0) * 1000,
            )
    
    async def _try_referer_google(self, url: str) -> BypassResult:
        """尝试 Google 来源伪装"""
        t0 = time.monotonic()
        try:
            if self._http:
                html = await self._http.fetch(
                    url,
                    headers={
                        "Referer": "https://www.google.com/",
                        "X-Forwarded-For": self._random_ip(),
                    }
                )
                if html and len(html) > 1000:
                    return BypassResult(
                        method=BypassMethod.REFERER_GOOGLE,
                        success=True,
                        html=html,
                        content_length=len(html),
                        elapsed_ms=(time.monotonic() - t0) * 1000,
                    )
            return BypassResult(
                method=BypassMethod.REFERER_GOOGLE,
                success=False,
                error="No content with Google referer",
                elapsed_ms=(time.monotonic() - t0) * 1000,
            )
        except Exception as e:
            return BypassResult(
                method=BypassMethod.REFERER_GOOGLE,
                success=False,
                error=str(e)[:200],
                elapsed_ms=(time.monotonic() - t0) * 1000,
            )
    
    async def _try_no_js(self, url: str) -> BypassResult:
        """尝试禁用 JS 版本（某些付费墙依赖 JS）"""
        t0 = time.monotonic()
        try:
            if self._http:
                # 某些站点有 noscript 版本
                noscript_url = url + "?noscript=1"
                html = await self._http.fetch(noscript_url)
                if html and len(html) > 1000:
                    return BypassResult(
                        method=BypassMethod.NO_JS,
                        success=True,
                        html=html,
                        content_length=len(html),
                        elapsed_ms=(time.monotonic() - t0) * 1000,
                    )
            return BypassResult(
                method=BypassMethod.NO_JS,
                success=False,
                error="No noscript version available",
                elapsed_ms=(time.monotonic() - t0) * 1000,
            )
        except Exception as e:
            return BypassResult(
                method=BypassMethod.NO_JS,
                success=False,
                error=str(e)[:200],
                elapsed_ms=(time.monotonic() - t0) * 1000,
            )
    
    async def _try_amp_version(self, url: str) -> list[BypassResult]:
        """尝试 AMP 版本"""
        results = []
        t0 = time.monotonic()
        
        amp_urls = self._url_transformer.to_amp_version(url)
        for amp_url in amp_urls[:2]:  # 只尝试前 2 个
            try:
                if self._http:
                    html = await self._http.fetch(amp_url)
                    if html and len(html) > 1000:
                        results.append(BypassResult(
                            method=BypassMethod.AMP_VERSION,
                            success=True,
                            html=html,
                            content_length=len(html),
                            elapsed_ms=(time.monotonic() - t0) * 1000,
                        ))
                        break
            except Exception:
                continue
        
        if not results:
            results.append(BypassResult(
                method=BypassMethod.AMP_VERSION,
                success=False,
                error="No AMP version available",
                elapsed_ms=(time.monotonic() - t0) * 1000,
            ))
        
        return results
    
    async def _try_print_version(self, url: str) -> list[BypassResult]:
        """尝试打印版本"""
        results = []
        t0 = time.monotonic()
        
        print_urls = self._url_transformer.to_print_version(url)
        for print_url in print_urls[:2]:
            try:
                if self._http:
                    html = await self._http.fetch(print_url)
                    if html and len(html) > 1000:
                        results.append(BypassResult(
                            method=BypassMethod.PRINT_VERSION,
                            success=True,
                            html=html,
                            content_length=len(html),
                            elapsed_ms=(time.monotonic() - t0) * 1000,
                        ))
                        break
            except Exception:
                continue
        
        if not results:
            results.append(BypassResult(
                method=BypassMethod.PRINT_VERSION,
                success=False,
                error="No print version available",
                elapsed_ms=(time.monotonic() - t0) * 1000,
            ))
        
        return results
    
    async def _try_rss_fulltext(self, url: str) -> BypassResult:
        """尝试从 RSS 获取全文"""
        t0 = time.monotonic()
        try:
            # 提取域名并尝试常见 RSS 路径
            domain = self._url_transformer.extract_domain(url)
            rss_urls = [
                f"https://{domain}/rss",
                f"https://{domain}/feed",
                f"https://{domain}/rss.xml",
                f"https://{domain}/atom.xml",
            ]
            
            if self._http:
                for rss_url in rss_urls:
                    try:
                        html = await self._http.fetch(rss_url)
                        if html and "<item>" in html:
                            return BypassResult(
                                method=BypassMethod.RSS_FULLTEXT,
                                success=True,
                                html=html,
                                content_length=len(html),
                                elapsed_ms=(time.monotonic() - t0) * 1000,
                            )
                    except Exception:
                        continue
            
            return BypassResult(
                method=BypassMethod.RSS_FULLTEXT,
                success=False,
                error="No RSS feed available",
                elapsed_ms=(time.monotonic() - t0) * 1000,
            )
        except Exception as e:
            return BypassResult(
                method=BypassMethod.RSS_FULLTEXT,
                success=False,
                error=str(e)[:200],
                elapsed_ms=(time.monotonic() - t0) * 1000,
            )
    
    @staticmethod
    def _random_ip() -> str:
        """生成随机 IP（用于 X-Forwarded-For）"""
        import random
        return f"{random.randint(1,255)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,255)}"


# ============================================================
# 高级突破策略
# ============================================================

class AdvancedBypass:
    """高级突破策略集合"""
    
    @staticmethod
    async def try_12ft_io(url: str, http_client=None) -> BypassResult:
        """尝试 12ft.io 付费墙绕过服务"""
        t0 = time.monotonic()
        try:
            bypass_url = f"https://12ft.io/{url}"
            if http_client:
                html = await http_client.fetch(bypass_url)
                if html and len(html) > 1000:
                    return BypassResult(
                        method="12ft_io",
                        success=True,
                        html=html,
                        content_length=len(html),
                        elapsed_ms=(time.monotonic() - t0) * 1000,
                    )
            return BypassResult(
                method="12ft_io",
                success=False,
                error="No content from 12ft.io",
                elapsed_ms=(time.monotonic() - t0) * 1000,
            )
        except Exception as e:
            return BypassResult(
                method="12ft_io",
                success=False,
                error=str(e)[:200],
                elapsed_ms=(time.monotonic() - t0) * 1000,
            )
    
    @staticmethod
    async def try_removepaywall(url: str, http_client=None) -> BypassResult:
        """尝试 removepaywall.com 服务"""
        t0 = time.monotonic()
        try:
            bypass_url = f"https://removepaywall.com/{url}"
            if http_client:
                html = await http_client.fetch(bypass_url)
                if html and len(html) > 1000:
                    return BypassResult(
                        method="removepaywall",
                        success=True,
                        html=html,
                        content_length=len(html),
                        elapsed_ms=(time.monotonic() - t0) * 1000,
                    )
            return BypassResult(
                method="removepaywall",
                success=False,
                error="No content from removepaywall.com",
                elapsed_ms=(time.monotonic() - t0) * 1000,
            )
        except Exception as e:
            return BypassResult(
                method="removepaywall",
                success=False,
                error=str(e)[:200],
                elapsed_ms=(time.monotonic() - t0) * 1000,
            )
    
    @staticmethod
    async def try_archive_today_save(url: str, http_client=None) -> BypassResult:
        """尝试 archive.today 保存新版本"""
        t0 = time.monotonic()
        try:
            # archive.today 的保存接口
            save_url = f"https://archive.ph/?run=1&url={quote_plus(url)}"
            if http_client:
                html = await http_client.fetch(save_url)
                if html and len(html) > 1000:
                    return BypassResult(
                        method="archive_today_save",
                        success=True,
                        html=html,
                        content_length=len(html),
                        elapsed_ms=(time.monotonic() - t0) * 1000,
                    )
            return BypassResult(
                method="archive_today_save",
                success=False,
                error="No content from archive.today save",
                elapsed_ms=(time.monotonic() - t0) * 1000,
            )
        except Exception as e:
            return BypassResult(
                method="archive_today_save",
                success=False,
                error=str(e)[:200],
                elapsed_ms=(time.monotonic() - t0) * 1000,
            )
    
    @staticmethod
    async def try_freedium(url: str, http_client=None) -> BypassResult:
        """尝试 freedium.cfd (Medium 付费墙绕过)"""
        t0 = time.monotonic()
        try:
            if "medium.com" in url:
                bypass_url = f"https://freedium.cfd/{url}"
                if http_client:
                    html = await http_client.fetch(bypass_url)
                    if html and len(html) > 1000:
                        return BypassResult(
                            method="freedium",
                            success=True,
                            html=html,
                            content_length=len(html),
                            elapsed_ms=(time.monotonic() - t0) * 1000,
                        )
            return BypassResult(
                method="freedium",
                success=False,
                error="Not a Medium URL or no content",
                elapsed_ms=(time.monotonic() - t0) * 1000,
            )
        except Exception as e:
            return BypassResult(
                method="freedium",
                success=False,
                error=str(e)[:200],
                elapsed_ms=(time.monotonic() - t0) * 1000,
            )
    
    @staticmethod
    async def try_reader_mode_api(url: str, http_client=None) -> BypassResult:
        """尝试浏览器 Reader Mode API"""
        t0 = time.monotonic()
        try:
            # 某些站点支持 ?output=amp 或 ?view=reader
            reader_urls = [
                f"{url}?output=amp",
                f"{url}?view=reader",
                f"{url}?amp=1",
                f"{url}&amp=1",
            ]
            
            if http_client:
                for reader_url in reader_urls:
                    try:
                        html = await http_client.fetch(reader_url)
                        if html and len(html) > 1000:
                            return BypassResult(
                                method="reader_mode_api",
                                success=True,
                                html=html,
                                content_length=len(html),
                                elapsed_ms=(time.monotonic() - t0) * 1000,
                            )
                    except Exception:
                        continue
            
            return BypassResult(
                method="reader_mode_api",
                success=False,
                error="No reader mode available",
                elapsed_ms=(time.monotonic() - t0) * 1000,
            )
        except Exception as e:
            return BypassResult(
                method="reader_mode_api",
                success=False,
                error=str(e)[:200],
                elapsed_ms=(time.monotonic() - t0) * 1000,
            )
    
    @staticmethod
    async def try_cookie_manipulation(url: str, http_client=None) -> BypassResult:
        """尝试 Cookie 操纵绕过付费墙"""
        t0 = time.monotonic()
        try:
            # 清除付费墙 Cookie，模拟新用户
            if http_client:
                html = await http_client.fetch(
                    url,
                    headers={
                        "Cookie": "",  # 清空 Cookie
                        "Cache-Control": "no-cache",
                        "Pragma": "no-cache",
                    }
                )
                if html and len(html) > 1000:
                    return BypassResult(
                        method="cookie_manipulation",
                        success=True,
                        html=html,
                        content_length=len(html),
                        elapsed_ms=(time.monotonic() - t0) * 1000,
                    )
            return BypassResult(
                method="cookie_manipulation",
                success=False,
                error="No content with cookie manipulation",
                elapsed_ms=(time.monotonic() - t0) * 1000,
            )
        except Exception as e:
            return BypassResult(
                method="cookie_manipulation",
                success=False,
                error=str(e)[:200],
                elapsed_ms=(time.monotonic() - t0) * 1000,
            )
    
    @staticmethod
    async def try_social_media_referer(url: str, http_client=None) -> BypassResult:
        """尝试社交媒体来源伪装"""
        t0 = time.monotonic()
        try:
            referers = [
                "https://www.facebook.com/",
                "https://t.co/",
                "https://twitter.com/",
                "https://www.reddit.com/",
                "https://news.ycombinator.com/",
            ]
            
            if http_client:
                for referer in referers:
                    try:
                        html = await http_client.fetch(
                            url,
                            headers={
                                "Referer": referer,
                                "X-Forwarded-For": BypassExecutor._random_ip(),
                            }
                        )
                        if html and len(html) > 1000:
                            return BypassResult(
                                method="social_media_referer",
                                success=True,
                                html=html,
                                content_length=len(html),
                                elapsed_ms=(time.monotonic() - t0) * 1000,
                            )
                    except Exception:
                        continue
            
            return BypassResult(
                method="social_media_referer",
                success=False,
                error="No content with social referer",
                elapsed_ms=(time.monotonic() - t0) * 1000,
            )
        except Exception as e:
            return BypassResult(
                method="social_media_referer",
                success=False,
                error=str(e)[:200],
                elapsed_ms=(time.monotonic() - t0) * 1000,
            )
    
    @staticmethod
    async def try_bot_user_agent(url: str, http_client=None) -> BypassResult:
        """尝试搜索引擎爬虫 User-Agent"""
        t0 = time.monotonic()
        try:
            bot_agents = [
                "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
                "Mozilla/5.0 (compatible; Bingbot/2.0; +http://www.bing.com/bingbot.htm)",
                "Mozilla/5.0 (compatible; Yahoo! Slurp; http://help.yahoo.com/help/us/ysearch/slurp)",
            ]
            
            if http_client:
                for agent in bot_agents:
                    try:
                        html = await http_client.fetch(
                            url,
                            headers={"User-Agent": agent}
                        )
                        if html and len(html) > 1000:
                            return BypassResult(
                                method="bot_user_agent",
                                success=True,
                                html=html,
                                content_length=len(html),
                                elapsed_ms=(time.monotonic() - t0) * 1000,
                            )
                    except Exception:
                        continue
            
            return BypassResult(
                method="bot_user_agent",
                success=False,
                error="No content with bot user agent",
                elapsed_ms=(time.monotonic() - t0) * 1000,
            )
        except Exception as e:
            return BypassResult(
                method="bot_user_agent",
                success=False,
                error=str(e)[:200],
                elapsed_ms=(time.monotonic() - t0) * 1000,
            )
