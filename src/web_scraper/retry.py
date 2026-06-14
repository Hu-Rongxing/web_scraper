# -*- coding: utf-8 -*-
"""
web_scraper/retry.py — 指数退避重试机制

处理:
  - 网络抖动 (TimeoutError, ConnectionError)
  - 浏览器崩溃 (TargetClosedError)
  - 页面加载失败
"""

import asyncio
import functools
from typing import Callable, Awaitable

from .config import logger


# 可重试的异常类型
RETRYABLE_EXCEPTIONS = (
    TimeoutError,
    ConnectionError,
    ConnectionRefusedError,
    ConnectionResetError,
    OSError,
)

# Playwright 特定异常 (如果不导入也能用)
RETRYABLE_ERROR_NAMES = {
    "TimeoutError",
    "TargetClosedError",
    "ProtocolError",
    "WebError",
}


def is_retryable(exception: Exception) -> bool:
    """判断异常是否可重试."""
    # 标准异常
    if isinstance(exception, RETRYABLE_EXCEPTIONS):
        return True

    # Playwright 异常 (通过类名匹配, 避免硬导入)
    error_name = type(exception).__name__
    if error_name in RETRYABLE_ERROR_NAMES:
        return True

    # 错误消息匹配
    msg = str(exception).lower()
    retry_hints = [
        "timeout",
        "connection",
        "target closed",
        "browser has been closed",
        "page crashed",
        "protocol error",
        "net::err_",
        "ns_error_net_",
    ]
    if any(hint in msg for hint in retry_hints):
        return True

    return False


async def retry_with_backoff(
    coro_fn: Callable[[], Awaitable],
    max_retries: int = 3,
    base_delay: float = 2.0,
    max_delay: float = 30.0,
    on_retry: Callable = None,
) -> Awaitable:
    """
    使用指数退避重试异步操作.

    Args:
        coro_fn: 返回 awaitable 的工厂函数
        max_retries: 最大重试次数 (不含首次)
        base_delay: 初始延迟 (秒)
        max_delay: 最大延迟 (秒)
        on_retry: 每次重试时的回调 (attempt, error) -> None

    Returns:
        coro_fn 的返回值

    Raises:
        最后一次尝试的异常 (如果所有重试都失败)
    """
    last_error = None

    for attempt in range(max_retries + 1):
        try:
            return await coro_fn()
        except Exception as e:
            last_error = e

            if attempt < max_retries and is_retryable(e):
                delay = min(base_delay * (2 ** attempt), max_delay)
                logger.warning(
                    "重试 %d/%d (%.1fs 后): %s",
                    attempt + 1, max_retries, delay, str(e)[:100],
                )
                if on_retry:
                    try:
                        on_retry(attempt + 1, e)
                    except Exception:
                        pass
                await asyncio.sleep(delay)
            else:
                if attempt < max_retries:
                    logger.error("不可重试的异常: %s", type(e).__name__)
                raise

    raise last_error  # type: ignore


def retry_decorator(max_retries: int = 3, base_delay: float = 2.0):
    """指数退避重试装饰器."""
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            async def _call():
                return await func(*args, **kwargs)
            return await retry_with_backoff(
                _call, max_retries=max_retries, base_delay=base_delay
            )
        return wrapper
    return decorator
