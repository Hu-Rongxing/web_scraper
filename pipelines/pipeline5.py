# -*- coding: utf-8 -*-
"""
pipelines/pipeline5.py — 管线5: nodriver 兜底链路

当管线1-4全部失败后，人工评估可启用管线5进行兜底抓取。
使用 nodriver (ultrafunkamsterdam/nodriver) + 正版Chrome。

注意: nodriver 在 Python 3.14 存在兼容性问题，需要降级使用或等待修复。
"""

import asyncio
import time

from ..config import (
    PAGE_WAIT_RENDER_MS,
    MIN_CONTENT_LENGTH,
    PIPELINE_FAILURE_SIGNALS,
    logger,
)


# ============================================================
# 管线5结果
from ..content_extractor import ContentExtractor
from ..models import Pipeline5Result


# ============================================================

class Pipeline5Manager:
    """
    管线5管理器: nodriver + 正版Chrome 兜底链路。
    
    特点:
    - 使用 ultrafunkamsterdam/nodriver (undetected-chromedriver 继任者)
    - 启动正版 Chrome 浏览器
    - 绕过 Cloudflare/DataDome 等高级反爬
    - 单次任务用完即毁，不复用会话
    
    注意:
    - 仅在管线1-4全部失败且人工评估后启用
    - 需要本地安装正版Chrome浏览器
    - nodriver 在 Python 3.14 存在兼容性问题
    """

    def __init__(self):
        self._browser = None
        self._started = False
        self._nodriver_available = False
        
        # 检查 nodriver 是否可用
        try:
            import nodriver
            self._nodriver_available = True
            logger.info("Pipeline5: nodriver available")
        except ImportError:
            logger.warning("Pipeline5: nodriver not installed, pipeline 5 disabled")
        except Exception as e:
            logger.warning("Pipeline5: nodriver import error: %s", e)

    async def start(self):
        """启动管线5管理器"""
        if not self._nodriver_available:
            logger.warning("Pipeline5: cannot start, nodriver not available")
            return
            
        if self._started:
            return
            
        try:
            import nodriver as uc
            # 启动正版 Chrome
            self._browser = await uc.start(
                headless=False,  # 管线5使用有头模式，更好绕过检测
                browser_args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--disable-blink-features=AutomationControlled",
                ],
            )
            self._started = True
            logger.info("Pipeline5 started: nodriver + Chrome ready")
        except Exception as e:
            logger.error("Pipeline5 start failed: %s", e)
            self._started = False

    async def shutdown(self):
        """关闭管线5管理器"""
        if not self._started:
            return
            
        if self._browser:
            try:
                self._browser.stop()
            except Exception as e:
                logger.warning("Pipeline5 shutdown error: %s", e)
                
        self._started = False
        logger.info("Pipeline5 shutdown")

    async def fetch(
        self,
        url: str,
        extract_strategy: str = "trafilatura",
        **opts,
    ) -> Pipeline5Result:
        """
        执行管线5抓取。
        
        Args:
            url: 目标 URL
            extract_strategy: 内容提取策略
            **opts: 其他选项
            
        Returns:
            Pipeline5Result
        """
        if not self._started:
            await self.start()
            
        if not self._started:
            return Pipeline5Result(
                url=url,
                success=False,
                error="Pipeline5: nodriver not available or failed to start",
                method="pipeline5:unavailable",
            )

        t0 = time.monotonic()
        page = None

        try:
            # 创建新标签页
            page = await self._browser.get(url)
            
            # 等待页面加载
            await asyncio.sleep(2)
            
            # 等待主要内容区域
            try:
                await page.select("article, main, .content, .app, #app", timeout=PAGE_WAIT_RENDER_MS / 1000)
            except Exception:
                pass

            # 模拟滚动
            for _ in range(3):
                await page.scroll_down(500)
                await asyncio.sleep(0.5)

            # 获取页面内容
            html = await page.get_content()
            title = await page.evaluate("document.title")

            # 失败判定
            if self._is_pipeline_failure(html):
                return Pipeline5Result(
                    url=url, final_url=page.url, html=html, title=title,
                    method="pipeline5:nodriver",
                    success=False,
                    error="Pipeline5: captcha/403/access denied",
                )

            # 内容提取
            extracted = ContentExtractor(strategy=extract_strategy).extract(html, url)

            if len(extracted.content) < MIN_CONTENT_LENGTH:
                return Pipeline5Result(
                    url=url, final_url=page.url, html=html, title=title,
                    method="pipeline5:nodriver",
                    success=False,
                    error=f"Pipeline5: content too short ({len(extracted.content)} chars)",
                )

            elapsed = (time.monotonic() - t0) * 1000
            logger.info("Pipeline5 success for %s (%.0fms)", url, elapsed)

            return Pipeline5Result(
                url=url, final_url=page.url,
                title=extracted.title or title, content=extracted.content, html=html,
                author=extracted.author, date=extracted.date,
                length=len(extracted.content), content_type="page",
                method="pipeline5:nodriver", success=True,
                elapsed_ms=elapsed,
            )

        except Exception as e:
            return Pipeline5Result(
                url=url, success=False,
                error=f"Pipeline5 exception: {str(e)[:200]}",
                method="pipeline5:error",
                elapsed_ms=(time.monotonic() - t0) * 1000,
            )
        finally:
            # 关闭标签页
            if page:
                try:
                    await page.close()
                except Exception:
                    pass

    def _is_pipeline_failure(self, html: str) -> bool:
        """判断 HTML 是否触发管线失败条件"""
        html_lower = html.lower()
        for signal in PIPELINE_FAILURE_SIGNALS:
            if signal in html_lower:
                return True
        return False

    @property
    def stats(self) -> dict:
        return {
            "started": self._started,
            "nodriver_available": self._nodriver_available,
        }
