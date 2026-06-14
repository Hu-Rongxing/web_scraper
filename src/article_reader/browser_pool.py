# -*- coding: utf-8 -*-
"""
article_reader/browser_pool.py — 三大独立 CloakBrowser 预加载浏览器池

v3.0: 池 A / 池 B / 池 C 完全隔离
  - 池 A: 管线 2 专用，短效住宅代理，无 humanize，快回收
  - 池 B: 管线 3 专用，静态绑定 IP，humanize 拟人，Profile 持久化
  - 池 C: 管线 4 专用，BPC 动态加载，单次即毁
"""

import asyncio
import time
import hashlib
import platform
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from .config import (
    BPC_EXTENSION_PATH,
    HEADLESS_DEFAULT,
    VIEWPORT,
    USER_AGENT,
    POOL_A_SIZE, POOL_A_MAX_PAGES, POOL_A_IDLE_TIMEOUT_SEC, POOL_A_PRELOAD,
    POOL_B_SIZE, POOL_B_MAX_PAGES, POOL_B_IDLE_TIMEOUT_SEC, POOL_B_PRELOAD,
    POOL_B_REBUILD_DAYS, POOL_B_PROFILE_ROOT, POOL_B_COOKIE_BACKUP_DIR,
    POOL_C_SIZE, HEALTH_CHECK_INTERVAL_SEC,
    logger,
)

# ---- CloakBrowser 检测 ----

try:
    import cloakbrowser
    from cloakbrowser import ProxySettings
    HAS_CLOAKBROWSER = True
    _CB_VERSION = getattr(cloakbrowser, "__version__", "unknown")
    logger.info("CloakBrowser %s available", _CB_VERSION)
except ImportError:
    HAS_CLOAKBROWSER = False
    ProxySettings = None
    logger.warning("CloakBrowser not installed! Browser pools will fail at runtime.")


# ============================================================
# Windows asyncio pipe 错误过滤器
# ============================================================

class _AsyncioPipeFilter:
    """
    过滤 Windows 上 Chromium 关闭时产生的无害 asyncio pipe 错误。
    避免控制台噪音，不影响实际功能。
    """
    
    _FILTERED_MESSAGES = [
        "I/O operation on closed pipe",
        "Pipe is closed",
        "Broken pipe",
    ]
    
    @classmethod
    def install(cls):
        """安装过滤器到 logging 系统"""
        import logging
        
        class PipeFilter(logging.Filter):
            def filter(self, record):
                msg = record.getMessage()
                return not any(f in msg for f in cls._FILTERED_MESSAGES)
        
        # 为 asyncio logger 添加过滤器
        asyncio_logger = logging.getLogger("asyncio")
        asyncio_logger.addFilter(PipeFilter())
        
        # 为 playwright/cloakbrowser logger 添加过滤器
        for name in ["playwright", "cloakbrowser"]:
            pkg_logger = logging.getLogger(name)
            if pkg_logger:
                pkg_logger.addFilter(PipeFilter())
        
        logger.debug("Installed asyncio pipe error filter for Windows")


# 在 Windows 上自动安装过滤器
if platform.system() == "Windows":
    _AsyncioPipeFilter.install()


# ============================================================
# 池类型枚举
# ============================================================

class PoolType:
    POOL_A = "pool_a"   # 管线 2：基础渲染
    POOL_B = "pool_b"   # 管线 3：高防护主力
    POOL_C = "pool_c"   # 管线 4：付费墙专项


# ============================================================
# 浏览器槽位
# ============================================================

@dataclass
class BrowserSlot:
    """浏览器池中的一个槽位"""
    pool_type: str = PoolType.POOL_A
    context: Optional[object] = None  # Playwright/CloakBrowser BrowserContext
    page_count: int = 0
    last_used: float = 0.0
    in_use: bool = False
    crashed: bool = False
    proxy_url: Optional[str] = None
    context_id: str = ""  # 唯一标识，用于池 B 绑定
    user_data_dir: Optional[Path] = None
    created_at: float = 0.0
    _cookie_backup_task: Optional[asyncio.Task] = None

    def mark_used(self):
        self.last_used = time.time()

    @property
    def idle_seconds(self) -> float:
        return time.time() - self.last_used

    @property
    def age_days(self) -> float:
        return (time.time() - self.created_at) / 86400


def _slot_stats(pool_name: str, slots: list[BrowserSlot], **extra) -> dict:
    stats = {
        "pool": pool_name,
        "total": len(slots),
        "in_use": sum(1 for slot in slots if slot.in_use),
        "available": sum(1 for slot in slots if not slot.in_use and slot.context),
    }
    stats.update(extra)
    return stats


# ============================================================
# 池 A：基础渲染（管线 2）
# ============================================================

class PoolA:
    """
    管线 2 专用池：
    - CloakBrowser 二进制，禁用 stealth 补丁
    - 关闭 humanize，无扩展
    - 短效住宅代理，IP 可轮换
    - 短生命周期，空闲快速回收
    """

    def __init__(
        self,
        size: int = POOL_A_SIZE,
        max_pages: int = POOL_A_MAX_PAGES,
        idle_timeout: int = POOL_A_IDLE_TIMEOUT_SEC,
        preload: bool = POOL_A_PRELOAD,
        proxy_provider=None,  # ResidentialRotatingPool 实例
    ):
        self._size = size
        self._max_pages = max_pages
        self._idle_timeout = idle_timeout
        self._preload = preload
        self._proxy_provider = proxy_provider

        self._slots: list[BrowserSlot] = []
        self._lock = asyncio.Lock()
        self._health_task: Optional[asyncio.Task] = None
        self._started = False
        self._slot_counter = 0

    async def start(self):
        if self._started:
            return
        self._started = True
        self._health_task = asyncio.create_task(self._health_check_loop())
        if self._preload:
            await self._preload_slots()
        logger.info("PoolA started: size=%d preload=%s", self._size, self._preload)

    async def shutdown(self):
        self._started = False
        if self._health_task:
            self._health_task.cancel()
            try:
                await self._health_task
            except asyncio.CancelledError:
                pass
        async with self._lock:
            for slot in self._slots:
                await self._close_slot(slot)
            self._slots.clear()
        logger.info("PoolA shutdown")

    async def acquire(self) -> BrowserSlot:
        """获取可用浏览器槽位"""
        while True:
            async with self._lock:
                # 复用空闲 slot
                for slot in self._slots:
                    if slot.in_use:
                        continue
                    if slot.page_count >= self._max_pages or slot.crashed:
                        await self._restart_slot(slot)
                    if slot.idle_seconds > self._idle_timeout:
                        await self._close_slot(slot)
                        self._slots.remove(slot)
                        continue
                    if slot.context:
                        slot.in_use = True
                        slot.mark_used()
                        return slot

                # 创建新 slot
                if len(self._slots) < self._size:
                    slot = await self._create_slot()
                    self._slots.append(slot)
                    slot.in_use = True
                    slot.mark_used()
                    return slot

            await asyncio.sleep(0.5)

    async def release(self, slot: BrowserSlot):
        """释放槽位"""
        async with self._lock:
            slot.in_use = False
            slot.page_count += 1
            slot.mark_used()
            if slot.page_count >= self._max_pages:
                slot.crashed = True
                await self._restart_slot(slot)

    # ---- 内部方法 ----

    async def _create_slot(self) -> BrowserSlot:
        self._slot_counter += 1
        context_id = f"pool_a_{id(self)}_{self._slot_counter}"
        user_data_dir = Path(tempfile.gettempdir()) / context_id
        user_data_dir.mkdir(parents=True, exist_ok=True)

        proxy_url = None
        if self._proxy_provider:
            proxy_url = await self._proxy_provider.acquire()

        proxy = ProxySettings(server=proxy_url) if proxy_url and ProxySettings else None

        args = ["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]

        context = await cloakbrowser.launch_persistent_context_async(
            user_data_dir=str(user_data_dir),
            headless=HEADLESS_DEFAULT,
            args=args,
            stealth_args=False,  # 禁用 stealth 补丁，全权由 CloakBrowser 内核
            proxy=proxy,
            user_agent=USER_AGENT,
            viewport=VIEWPORT,
            locale="en-US",
            humanize=False,  # 池 A 关闭拟人
        )

        # 启动时校验 stealth 状态
        await self._verify_stealth(context)
        
        # 代理 IP 泄露检测
        if proxy_url:
            await self._verify_proxy_ip(context, proxy_url)

        return BrowserSlot(
            pool_type=PoolType.POOL_A,
            context=context,
            context_id=context_id,
            proxy_url=proxy_url,
            user_data_dir=user_data_dir,
            last_used=time.time(),
            created_at=time.time(),
        )

    async def _verify_proxy_ip(self, context, proxy_url: str):
        """验证代理 IP 是否泄露（检查出口 IP 是否与预期一致）"""
        try:
            page = await context.new_page()
            await page.goto("https://api.ipify.org?format=json", wait_until="domcontentloaded", timeout=10000)
            content = await page.content()
            await page.close()
            
            # 解析返回的 IP
            import json
            data = json.loads(content)
            actual_ip = data.get("ip", "")
            
            # 从 proxy_url 提取预期 IP（简化处理，实际可能需要更复杂的逻辑）
            # 这里仅记录日志，不阻断流程
            logger.debug("PoolA: proxy IP check - actual=%s, proxy=%s", actual_ip, proxy_url[:50])
        except Exception as e:
            logger.warning("PoolA: proxy IP verification failed: %s", e)

    async def _restart_slot(self, slot: BrowserSlot):
        await self._close_slot(slot)
        new_slot = await self._create_slot()
        slot.context = new_slot.context
        slot.user_data_dir = new_slot.user_data_dir
        slot.context_id = new_slot.context_id
        slot.proxy_url = new_slot.proxy_url
        slot.page_count = 0
        slot.crashed = False
        slot.last_used = time.time()
        slot.created_at = time.time()

    async def _close_slot(self, slot: BrowserSlot):
        if slot.context:
            try:
                await slot.context.close()
            except Exception as e:
                logger.warning("PoolA close context error: %s", e)
            slot.context = None
        if slot.proxy_url and self._proxy_provider:
            await self._proxy_provider.release(slot.proxy_url)
        if slot.user_data_dir and slot.user_data_dir.exists():
            shutil.rmtree(slot.user_data_dir, ignore_errors=True)

    async def _preload_slots(self):
        logger.info("PoolA: preloading %d slots...", self._size)
        for i in range(self._size):
            try:
                slot = await self._create_slot()
                async with self._lock:
                    self._slots.append(slot)
                logger.info("PoolA: preloaded slot %d/%d", i + 1, self._size)
                # Small delay to avoid Chromium concurrent launch conflicts
                if i < self._size - 1:
                    await asyncio.sleep(1)
            except Exception as e:
                logger.error("PoolA: preload slot %d failed: %s", i + 1, e)

    async def _verify_stealth(self, context):
        """Verify stealth status on startup"""
        try:
            page = await context.new_page()
            await page.goto("about:blank")
            result = await page.evaluate("""
                () => {
                    const webdriver = navigator.webdriver;
                    const descriptor = Object.getOwnPropertyDescriptor(navigator, 'webdriver');
                    return {
                        webdriver: webdriver,
                        descriptor_configurable: descriptor ? descriptor.configurable : null,
                        descriptor_writable: descriptor ? descriptor.writable : null,
                    };
                }
            """)
            await page.close()
            if result.get('webdriver') is not False:
                logger.warning("PoolA: stealth check failed - navigator.webdriver=%s", result.get('webdriver'))
            else:
                logger.debug("PoolA: stealth check passed - navigator.webdriver=false")
        except Exception as e:
            logger.warning("PoolA: stealth check error: %s", e)

    async def _health_check_loop(self):
        while self._started:
            try:
                async with self._lock:
                    for slot in list(self._slots):
                        if slot.in_use:
                            continue
                        if slot.crashed:
                            await self._restart_slot(slot)
                        elif slot.idle_seconds > self._idle_timeout:
                            await self._close_slot(slot)
                            self._slots.remove(slot)
            except Exception as e:
                logger.error("PoolA health check error: %s", e)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL_SEC)

    @property
    def stats(self) -> dict:
        return _slot_stats("A", self._slots)


# ============================================================
# 池 B：高防护主力（管线 3）
# ============================================================

class PoolB:
    """
    管线 3 专用池：
    - CloakBrowser + humanize 拟人
    - 静态独享 IP，与上下文永久绑定
    - Profile 持久化：./browser_profile/pool_b/{代理IP哈希}/{站点域名哈希}/
    - 14 天重建，每日 Cookie 备份
    """

    def __init__(
        self,
        size: int = POOL_B_SIZE,
        max_pages: int = POOL_B_MAX_PAGES,
        idle_timeout: int = POOL_B_IDLE_TIMEOUT_SEC,
        preload: bool = POOL_B_PRELOAD,
        rebuild_days: int = POOL_B_REBUILD_DAYS,
        proxy_provider=None,  # StaticBoundPool 实例
    ):
        self._size = size
        self._max_pages = max_pages
        self._idle_timeout = idle_timeout
        self._preload = preload
        self._rebuild_days = rebuild_days
        self._proxy_provider = proxy_provider

        self._slots: list[BrowserSlot] = []
        self._lock = asyncio.Lock()
        self._health_task: Optional[asyncio.Task] = None
        self._cookie_backup_task: Optional[asyncio.Task] = None
        self._started = False
        self._slot_counter = 0

    async def start(self):
        if self._started:
            return
        self._started = True
        self._health_task = asyncio.create_task(self._health_check_loop())
        self._cookie_backup_task = asyncio.create_task(self._daily_cookie_backup_loop())
        if self._preload:
            await self._preload_slots()
        logger.info("PoolB started: size=%d rebuild=%dd", self._size, self._rebuild_days)

    async def shutdown(self):
        self._started = False
        for task in [self._health_task, self._cookie_backup_task]:
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        async with self._lock:
            for slot in self._slots:
                await self._close_slot(slot, destroy_profile=False)
            self._slots.clear()
        logger.info("PoolB shutdown")

    async def acquire(self, site_domain: str = "") -> BrowserSlot:
        """
        获取可用浏览器槽位。
        site_domain 用于匹配已有的持久化 Profile。
        """
        while True:
            async with self._lock:
                # 优先复用已有同站点 slot
                for slot in self._slots:
                    if slot.in_use:
                        continue
                    if slot.page_count >= self._max_pages or slot.crashed:
                        await self._restart_slot(slot)
                    if slot.age_days >= self._rebuild_days:
                        logger.info("PoolB: slot %s reached %d days, rebuilding", slot.context_id, self._rebuild_days)
                        await self._restart_slot(slot)
                    if slot.context:
                        slot.in_use = True
                        slot.mark_used()
                        return slot

                # 创建新 slot
                if len(self._slots) < self._size:
                    slot = await self._create_slot(site_domain)
                    self._slots.append(slot)
                    slot.in_use = True
                    slot.mark_used()
                    return slot

            await asyncio.sleep(0.5)

    async def release(self, slot: BrowserSlot):
        async with self._lock:
            slot.in_use = False
            slot.page_count += 1
            slot.mark_used()

    # ---- 内部方法 ----

    def _get_profile_dir(self, proxy_url: str, site_domain: str = "", slot_idx: int = 0) -> Path:
        """
        计算持久化 Profile 目录路径。
        规则: ./browser_profile/pool_b/{代理IP}/{站点域名哈希}_{slot_idx}/
        IP 直接使用原始代理地址（去除协议和认证），站点域名用 MD5 哈希。
        每个 slot 必须有独立目录，避免 Chromium user-data-dir 冲突。
        """
        # 从代理 URL 提取 IP:port 部分作为目录名
        if proxy_url:
            # socks5://user:pass@1.2.3.4:1080 → 1.2.3.4_1080
            parsed = urlparse(proxy_url)
            ip_part = f"{parsed.hostname}_{parsed.port}" if parsed.hostname else "no_proxy"
        else:
            ip_part = "no_proxy"
        domain_hash = hashlib.md5(site_domain.encode()).hexdigest()[:12] if site_domain else "default"
        # 加入 slot_idx 保证每个 slot 目录唯一
        profile_dir = POOL_B_PROFILE_ROOT / ip_part / f"{domain_hash}_{slot_idx}"
        profile_dir.mkdir(parents=True, exist_ok=True)
        return profile_dir

    async def _create_slot(self, site_domain: str = "") -> BrowserSlot:
        self._slot_counter += 1
        slot_idx = self._slot_counter

        # 获取静态绑定 IP
        context_id = f"pool_b_{id(self)}_{slot_idx}"
        proxy_url = None
        if self._proxy_provider:
            proxy_url = await self._proxy_provider.acquire_for_context(context_id)

        # 持久化 Profile 目录（每个 slot 必须唯一，避免 Chromium user-data-dir 冲突）
        user_data_dir = self._get_profile_dir(proxy_url or "no_proxy", site_domain, slot_idx)

        proxy = ProxySettings(server=proxy_url) if proxy_url and ProxySettings else None

        args = ["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]

        context = await cloakbrowser.launch_persistent_context_async(
            user_data_dir=str(user_data_dir),
            headless=HEADLESS_DEFAULT,
            args=args,
            stealth_args=False,  # 禁用 stealth 补丁，CloakBrowser 内核控制
            proxy=proxy,
            user_agent=USER_AGENT,
            viewport=VIEWPORT,
            locale="en-US",
            humanize=True,  # 池 B 开启拟人
            human_preset="default",
        )

        # 启动时校验 stealth 状态
        await self._verify_stealth(context)

        return BrowserSlot(
            pool_type=PoolType.POOL_B,
            context=context,
            context_id=context_id,
            proxy_url=proxy_url,
            user_data_dir=user_data_dir,
            last_used=time.time(),
            created_at=time.time(),
        )

    async def _verify_stealth(self, context):
        """启动时校验 stealth 状态，确保 navigator.webdriver=false"""
        try:
            page = await context.new_page()
            await page.goto("about:blank")
            result = await page.evaluate("""
                () => {
                    const webdriver = navigator.webdriver;
                    const descriptor = Object.getOwnPropertyDescriptor(navigator, 'webdriver');
                    return {
                        webdriver: webdriver,
                        descriptor_configurable: descriptor ? descriptor.configurable : null,
                        descriptor_writable: descriptor ? descriptor.writable : null,
                    };
                }
            """)
            await page.close()
            if result.get('webdriver') is not False:
                logger.warning("PoolB: stealth check failed - navigator.webdriver=%s", result.get('webdriver'))
            else:
                logger.debug("PoolB: stealth check passed - navigator.webdriver=false")
        except Exception as e:
            logger.warning("PoolB: stealth check error: %s", e)

    async def _restart_slot(self, slot: BrowserSlot):
        """重建 slot，保留 Profile 目录（继承 Cookie/LocalStorage）"""
        logger.info("PoolB: rebuilding slot %s (preserving profile)", slot.context_id)
        # 关闭 context 但不删除 profile 目录
        if slot.context:
            try:
                await slot.context.close()
            except Exception:
                pass
            slot.context = None

        # 清理临时缓存（保留 Cookie/LocalStorage）
        if slot.user_data_dir:
            for cache_dir in ["Cache", "Code Cache", "GPUCache", "Service Worker"]:
                cache_path = slot.user_data_dir / cache_dir
                if cache_path.exists():
                    shutil.rmtree(cache_path, ignore_errors=True)

        # 释放旧绑定，重新创建
        if self._proxy_provider and slot.proxy_url:
            await self._proxy_provider.release_context(slot.context_id)

        new_slot = await self._create_slot("")
        slot.context = new_slot.context
        slot.context_id = new_slot.context_id
        slot.proxy_url = new_slot.proxy_url
        slot.user_data_dir = new_slot.user_data_dir
        slot.page_count = 0
        slot.crashed = False
        slot.last_used = time.time()
        slot.created_at = time.time()

    async def _close_slot(self, slot: BrowserSlot, destroy_profile: bool = False):
        if slot.context:
            try:
                await slot.context.close()
            except Exception:
                pass
            slot.context = None
        if self._proxy_provider:
            await self._proxy_provider.release_context(slot.context_id)
        if destroy_profile and slot.user_data_dir and slot.user_data_dir.exists():
            shutil.rmtree(slot.user_data_dir, ignore_errors=True)

    async def _preload_slots(self):
        logger.info("PoolB: preloading %d slots...", self._size)
        for i in range(self._size):
            try:
                slot = await self._create_slot("")
                async with self._lock:
                    self._slots.append(slot)
                logger.info("PoolB: preloaded slot %d/%d", i + 1, self._size)
                # Small delay to avoid Chromium concurrent launch conflicts
                if i < self._size - 1:
                    await asyncio.sleep(1)
            except Exception as e:
                logger.error("PoolB: preload slot %d failed: %s", i + 1, e)

    async def _health_check_loop(self):
        """健康检查：定期检测 slot 状态，重建崩溃或超龄 slot"""
        while self._started:
            try:
                await asyncio.sleep(60)  # 每分钟检查
                async with self._lock:
                    for slot in list(self._slots):
                        if slot.in_use:
                            continue
                        if slot.crashed:
                            logger.info("PoolB: rebuilding crashed slot %s", slot.context_id)
                            await self._restart_slot(slot)
                        elif slot.age_days >= self._rebuild_days:
                            logger.info("PoolB: slot %s reached %d days, rebuilding", slot.context_id, self._rebuild_days)
                            await self._restart_slot(slot)
                        elif slot.idle_seconds > self._idle_timeout:
                            logger.info("PoolB: closing idle slot %s (%.0fs)", slot.context_id, slot.idle_seconds)
                            await self._close_slot(slot, destroy_profile=False)
                            self._slots.remove(slot)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("PoolB health check error: %s", e)

    async def _daily_cookie_backup_loop(self):
        """每日 Cookie 备份"""
        while self._started:
            try:
                await asyncio.sleep(86400)  # 24h
                await self._backup_all_cookies()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("PoolB cookie backup error: %s", e)

    async def _backup_all_cookies(self):
        """导出所有 slot 的 Cookie 为 Netscape 格式"""
        POOL_B_COOKIE_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        async with self._lock:
            for slot in self._slots:
                if not slot.context:
                    continue
                try:
                    # Playwright/CloakBrowser context 的 cookies 导出
                    cookies = await slot.context.cookies()
                    if not cookies:
                        continue
                    # 转换为 Netscape 格式
                    netscape_lines = ["# Netscape HTTP Cookie File", "# https://curl.haxx.se/docs/http-cookies.html", ""]
                    for cookie in cookies:
                        # 格式: domain\tflag\tpath\tsecure\texpiration\tname\tvalue
                        domain = cookie.get('domain', '')
                        flag = 'TRUE' if domain.startswith('.') else 'FALSE'
                        path = cookie.get('path', '/')
                        secure = 'TRUE' if cookie.get('secure', False) else 'FALSE'
                        expires = str(int(cookie.get('expires', 0)))
                        name = cookie.get('name', '')
                        value = cookie.get('value', '')
                        netscape_lines.append(f"{domain}\t{flag}\t{path}\t{secure}\t{expires}\t{name}\t{value}")
                    backup_file = POOL_B_COOKIE_BACKUP_DIR / f"{slot.context_id}_{int(time.time())}.txt"
                    with open(backup_file, "w", encoding="utf-8") as f:
                        f.write("\n".join(netscape_lines))
                    logger.info("PoolB: backed up %d cookies (Netscape) for %s", len(cookies), slot.context_id)
                except Exception as e:
                    logger.warning("PoolB: cookie backup failed for %s: %s", slot.context_id, e)

    async def restore_cookies(self, slot: BrowserSlot, backup_file: Path):
        """从 Netscape 格式备份恢复 Cookie"""
        if not backup_file.exists():
            return
        try:
            # 解析 Netscape 格式
            cookies = []
            with open(backup_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    parts = line.split("\t")
                    if len(parts) >= 7:
                        domain, flag, path, secure, expires, name, value = parts[:7]
                        cookies.append({
                            "name": name,
                            "value": value,
                            "domain": domain,
                            "path": path,
                            "secure": secure == "TRUE",
                            "expires": int(expires) if expires.isdigit() else 0,
                        })
            if cookies:
                await slot.context.add_cookies(cookies)
                logger.info("PoolB: restored %d cookies (Netscape) for %s", len(cookies), slot.context_id)
        except Exception as e:
            logger.warning("PoolB: cookie restore failed: %s", e)

    @property
    def stats(self) -> dict:
        return _slot_stats("B", self._slots, rebuild_days=self._rebuild_days)


# ============================================================
# 池 C：付费墙专项（管线 4）
# ============================================================

class PoolC:
    """
    管线 4 专用池：
    - CloakBrowser + humanize
    - CDP 动态加载 BPC 扩展
    - 付费墙专用独享 IP，与池 A/B 隔离
    - 单次任务用完即毁，不复用 Profile/Cookie/扩展
    """

    def __init__(
        self,
        size: int = POOL_C_SIZE,
        proxy_provider=None,  # StaticBoundPool 实例（PROXY_GROUP_3B）
    ):
        self._size = size
        self._proxy_provider = proxy_provider
        self._slots: list[BrowserSlot] = []
        self._lock = asyncio.Lock()
        self._started = False
        self._slot_counter = 0

    async def start(self):
        if self._started:
            return
        self._started = True
        logger.info("PoolC started: size=%d (ephemeral, no preload)", self._size)

    async def shutdown(self):
        self._started = False
        async with self._lock:
            for slot in self._slots:
                await self._destroy_slot(slot)
            self._slots.clear()
        logger.info("PoolC shutdown")

    async def acquire(self) -> BrowserSlot:
        """Create a one-shot browser slot and respect the pool concurrency limit."""
        while True:
            async with self._lock:
                active = sum(1 for slot in self._slots if slot.in_use)
                if active < self._size:
                    break
            await asyncio.sleep(0.5)

        slot = await self._create_ephemeral_slot()
        async with self._lock:
            self._slots.append(slot)
            slot.in_use = True
            slot.mark_used()
        return slot

    async def release_and_destroy(self, slot: BrowserSlot):
        """释放并彻底销毁（池 C 核心规则）"""
        async with self._lock:
            slot.in_use = False
            await self._destroy_slot(slot)
            if slot in self._slots:
                self._slots.remove(slot)

    # ---- 内部方法 ----

    async def _create_ephemeral_slot(self) -> BrowserSlot:
        """创建临时浏览器实例，加载 BPC 扩展"""
        self._slot_counter += 1
        context_id = f"pool_c_{id(self)}_{self._slot_counter}"

        # 临时 user_data_dir
        user_data_dir = Path(tempfile.gettempdir()) / context_id
        user_data_dir.mkdir(parents=True, exist_ok=True)

        # 付费墙专属代理
        proxy_url = None
        if self._proxy_provider:
            proxy_url = await self._proxy_provider.acquire_for_context(context_id)
        proxy = ProxySettings(server=proxy_url) if proxy_url and ProxySettings else None

        args = ["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]

        # 动态加载 BPC 扩展
        if BPC_EXTENSION_PATH.exists():
            args.append(f"--disable-extensions-except={BPC_EXTENSION_PATH}")
            args.append(f"--load-extension={BPC_EXTENSION_PATH}")

        context = await cloakbrowser.launch_persistent_context_async(
            user_data_dir=str(user_data_dir),
            headless=HEADLESS_DEFAULT,
            args=args,
            stealth_args=False,
            proxy=proxy,
            user_agent=USER_AGENT,
            viewport=VIEWPORT,
            locale="en-US",
            humanize=True,  # 池 C 开启拟人
            human_preset="default",
        )

        # 启动时校验 stealth 状态
        await self._verify_stealth(context)

        return BrowserSlot(
            pool_type=PoolType.POOL_C,
            context=context,
            context_id=context_id,
            proxy_url=proxy_url,
            user_data_dir=user_data_dir,
            last_used=time.time(),
            created_at=time.time(),
        )

    async def _verify_stealth(self, context):
        """Verify stealth status on startup"""
        try:
            page = await context.new_page()
            await page.goto("about:blank")
            result = await page.evaluate("""
                () => ({
                    webdriver: navigator.webdriver,
                    plugins: navigator.plugins.length,
                    languages: navigator.languages.length
                })
            """)
            await page.close()
            if result.get('webdriver') is not False:
                logger.warning("PoolC: stealth check failed - navigator.webdriver=%s", result.get('webdriver'))
            else:
                logger.debug("PoolC: stealth check passed - navigator.webdriver=false")
        except Exception as e:
            logger.warning("PoolC: stealth check error: %s", e)

    async def _destroy_slot(self, slot: BrowserSlot):
        """彻底销毁：关闭 context + 删除 Profile + 释放代理"""
        if slot.context:
            try:
                await slot.context.close()
            except Exception:
                pass
            slot.context = None
        if self._proxy_provider:
            await self._proxy_provider.release_context(slot.context_id)
        if slot.user_data_dir and slot.user_data_dir.exists():
            shutil.rmtree(slot.user_data_dir, ignore_errors=True)
        logger.debug("PoolC: destroyed slot %s", slot.context_id)

    @property
    def stats(self) -> dict:
        return _slot_stats("C", self._slots, ephemeral=True)


# ============================================================
# 向后兼容别名
# ============================================================

class BrowserEngine:
    CLOAKBROWSER = "cloakbrowser"
    PLAYWRIGHT = "playwright"
    AUTO = "auto"
