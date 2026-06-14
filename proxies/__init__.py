# -*- coding: utf-8 -*-
"""
proxies/ — 三组独立代理池管理

组 1 (PipelineProxyPool): 管线 1 HTTP 请求，数据中心代理，轮询
组 2 (ResidentialRotatingPool): 池 A / 管线 2，短效住宅代理，自动剔除失效 IP
组 3 (StaticBoundPool): 池 B / 池 C，静态独享 IP，与浏览器上下文一一绑定
"""

from .proxy_pool import (
    ProxyGroup,
    PipelineProxyPool,
    ResidentialRotatingPool,
    StaticBoundPool,
    ProxyHealthChecker,
)

__all__ = [
    "ProxyGroup",
    "PipelineProxyPool",
    "ResidentialRotatingPool",
    "StaticBoundPool",
    "ProxyHealthChecker",
]
