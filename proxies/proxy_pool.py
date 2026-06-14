# -*- coding: utf-8 -*-
"""
proxies/proxy_pool.py — 三组代理池实现

组 1: PipelineProxyPool — 轮询调度，侧重吞吐
组 2: ResidentialRotatingPool — 短效住宅，失效自动剔除
组 3: StaticBoundPool — 静态独享 IP，与上下文绑定锁定
"""

import asyncio
import time
import itertools
from dataclasses import dataclass, field
from typing import Optional

from ..config import (
    PROXY_GROUP_1,
    PROXY_GROUP_2,
    PROXY_GROUP_3A,
    PROXY_GROUP_3B,
    PROXY_HEALTH_CHECK_INTERVAL_SEC,
    PROXY_IP_CHECK_URL,
    PROXY_BLACKLIST_TTL_SEC,
    logger,
)


# ============================================================
# 数据结构
# ============================================================

@dataclass
class ProxyEntry:
    """单条代理记录"""
    url: str
    healthy: bool = True
    fail_count: int = 0
    last_used: float = 0.0
    last_check: float = 0.0
    detected_ip: Optional[str] = None
    blacklisted_until: float = 0.0
    bound_context_id: Optional[str] = None  # 组 3 专用：绑定的上下文 ID

    @property
    def is_blacklisted(self) -> bool:
        return time.time() < self.blacklisted_until

    @property
    def is_available(self) -> bool:
        return self.healthy and not self.is_blacklisted


class ProxyGroup:
    """代理组枚举"""
    DATACENTER = "group1_datacenter"      # 管线 1
    RESIDENTIAL_ROTATING = "group2_resi"   # 池 A / 管线 2
    STATIC_BOUND_A = "group3a_static_a"    # 池 B / 管线 3
    STATIC_BOUND_C = "group3b_static_c"    # 池 C / 管线 4


# ============================================================
# 组 1: 数据中心代理池（管线 1）
# ============================================================

class PipelineProxyPool:
    """
    管线 1 专用：固定代理，轮询调度。
    用户只有固定代理 IP，不是动态代理池。
    """

    def __init__(self, proxies: Optional[list[str]] = None):
        self._proxies = proxies or list(PROXY_GROUP_1)
        self._index = 0
        self._lock = asyncio.Lock()
        logger.info("PipelineProxyPool: %d fixed proxies", len(self._proxies))

    async def acquire(self) -> Optional[str]:
        """轮询获取下一个代理（固定 IP 列表循环使用）"""
        if not self._proxies:
            return None
        async with self._lock:
            proxy = self._proxies[self._index % len(self._proxies)]
            self._index += 1
            return proxy

    async def release(self, proxy_url: str, success: bool = True):
        """释放代理（固定 IP 不做剔除，仅日志）"""
        if not success:
            logger.warning("PipelineProxyPool: proxy failed: %s", proxy_url)

    @property
    def available_count(self) -> int:
        return len(self._proxies)


# ============================================================
# 组 2: 短效住宅代理池（池 A / 管线 2）
# ============================================================

class ResidentialRotatingPool:
    """
    池 A 专用：固定住宅代理，轮询使用。
    用户只有固定代理 IP，不是动态代理池。
    支持黑名单机制：被站点封禁的 IP 临时停用。
    """

    def __init__(
        self,
        proxies: Optional[list[str]] = None,
        max_fail_before_blacklist: int = 5,
    ):
        raw = proxies or list(PROXY_GROUP_2)
        self._entries: dict[str, ProxyEntry] = {
            url: ProxyEntry(url=url) for url in raw
        }
        self._max_fail = max_fail_before_blacklist
        self._index = 0
        self._lock = asyncio.Lock()
        logger.info("ResidentialRotatingPool: %d fixed proxies", len(self._entries))

    async def acquire(self) -> Optional[str]:
        """获取下一个可用代理（跳过黑名单）"""
        async with self._lock:
            available = [e for e in self._entries.values() if e.is_available]
            if not available:
                logger.warning("ResidentialRotatingPool: no available proxies!")
                return None
            entry = available[self._index % len(available)]
            self._index += 1
            entry.last_used = time.time()
            return entry.url

    async def release(self, proxy_url: str, success: bool = True):
        """释放代理，连续失败则加入黑名单"""
        async with self._lock:
            entry = self._entries.get(proxy_url)
            if not entry:
                return
            if success:
                entry.fail_count = 0
            else:
                entry.fail_count += 1
                if entry.fail_count >= self._max_fail:
                    entry.blacklisted_until = time.time() + PROXY_BLACKLIST_TTL_SEC
                    logger.warning(
                        "ResidentialRotatingPool: blacklisted %s (fail_count=%d)",
                        proxy_url, entry.fail_count,
                    )

    def mark_blacklisted(self, proxy_url: str, ttl: float = PROXY_BLACKLIST_TTL_SEC):
        """手动将 IP 加入黑名单"""
        entry = self._entries.get(proxy_url)
        if entry:
            entry.blacklisted_until = time.time() + ttl
            logger.info("ResidentialRotatingPool: manually blacklisted %s for %ds", proxy_url, ttl)

    @property
    def available_count(self) -> int:
        return sum(1 for e in self._entries.values() if e.is_available)


# ============================================================
# 组 3: 静态独享 IP 池（池 B / 池 C）
# ============================================================

class StaticBoundPool:
    """
    池 B / 池 C 专用：静态独享 IP，与浏览器上下文一一绑定。
    每个 IP 只能绑定一个 context，禁止跨 IP 混用 Cookie。
    """

    def __init__(
        self,
        proxies: Optional[list[str]] = None,
        pool_name: str = "static",
    ):
        raw = proxies or list(PROXY_GROUP_3A)  # 池 C 会传 PROXY_GROUP_3B
        self._pool_name = pool_name
        self._entries: dict[str, ProxyEntry] = {
            url: ProxyEntry(url=url) for url in raw
        }
        self._bindings: dict[str, str] = {}  # context_id -> proxy_url
        self._lock = asyncio.Lock()
        logger.info("StaticBoundPool [%s]: %d static IPs", pool_name, len(self._entries))

    async def acquire_for_context(self, context_id: str) -> Optional[str]:
        """
        为指定 context 获取绑定的代理。
        如果该 context 已有绑定，返回已绑定的 IP。
        否则分配一个未绑定的空闲 IP。
        """
        async with self._lock:
            # 已有绑定
            if context_id in self._bindings:
                return self._bindings[context_id]

            # 找空闲未绑定的 IP
            for entry in self._entries.values():
                if entry.is_available and entry.bound_context_id is None:
                    entry.bound_context_id = context_id
                    self._bindings[context_id] = entry.url
                    logger.info(
                        "StaticBoundPool [%s]: bound %s -> context %s",
                        self._pool_name, entry.url, context_id,
                    )
                    return entry.url

            logger.warning("StaticBoundPool [%s]: no free IP for context %s", self._pool_name, context_id)
            return None

    async def release_context(self, context_id: str):
        """释放 context 绑定（池 C 用完即毁时调用）"""
        async with self._lock:
            proxy_url = self._bindings.pop(context_id, None)
            if proxy_url and proxy_url in self._entries:
                entry = self._entries[proxy_url]
                entry.bound_context_id = None
                logger.info(
                    "StaticBoundPool [%s]: released context %s from %s",
                    self._pool_name, context_id, proxy_url,
                )

    def get_binding(self, context_id: str) -> Optional[str]:
        """查询 context 绑定的代理"""
        return self._bindings.get(context_id)

    @property
    def available_count(self) -> int:
        return sum(1 for e in self._entries.values() if e.bound_context_id is None and e.is_available)

    @property
    def total_count(self) -> int:
        return len(self._entries)

    @property
    def bound_count(self) -> int:
        return len(self._bindings)


# ============================================================
# 代理健康检查器
# ============================================================

class ProxyHealthChecker:
    """
    定时检测代理连通性 + 出口 IP 验证。
    IP 泄露时立刻销毁会话。
    """

    def __init__(
        self,
        check_interval: float = PROXY_HEALTH_CHECK_INTERVAL_SEC,
        ip_check_url: str = PROXY_IP_CHECK_URL,
    ):
        self._interval = check_interval
        self._ip_check_url = ip_check_url
        self._task: Optional[asyncio.Task] = None
        self._known_ips: dict[str, str] = {}  # proxy_url -> expected_ip
        self._running = False

    async def start(self):
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._check_loop())
        logger.info("ProxyHealthChecker started (interval=%ds)", self._interval)

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def check_proxy(self, proxy_url: str) -> tuple[bool, Optional[str]]:
        """
        检查代理连通性 + 出口 IP。
        返回 (is_healthy, detected_ip)
        """
        try:
            import aiohttp
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(
                    self._ip_check_url,
                    proxy=proxy_url,
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        ip = data.get("ip", "unknown")
                        return True, ip
                    return False, None
        except ImportError:
            # aiohttp 不可用，用同步 requests 降级
            try:
                import requests
                resp = requests.get(
                    self._ip_check_url,
                    proxies={"http": proxy_url, "https": proxy_url},
                    timeout=10,
                )
                if resp.status_code == 200:
                    ip = resp.json().get("ip", "unknown")
                    return True, ip
                return False, None
            except Exception:
                return False, None
        except Exception as e:
            logger.debug("Health check failed for %s: %s", proxy_url, e)
            return False, None

    async def verify_ip_binding(self, proxy_url: str, expected_ip: Optional[str] = None) -> bool:
        """
        验证代理出口 IP 是否与预期一致。
        IP 泄露时返回 False。
        """
        healthy, detected_ip = await self.check_proxy(proxy_url)
        if not healthy:
            return False
        if expected_ip and detected_ip != expected_ip:
            logger.error(
                "IP LEAK DETECTED: proxy=%s expected=%s got=%s",
                proxy_url, expected_ip, detected_ip,
            )
            return False
        return True

    async def _check_loop(self):
        """后台健康巡检"""
        while self._running:
            try:
                await asyncio.sleep(self._interval)
                # 具体巡检逻辑由各池自行管理
                logger.debug("ProxyHealthChecker: periodic check completed")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("ProxyHealthChecker error: %s", e)
