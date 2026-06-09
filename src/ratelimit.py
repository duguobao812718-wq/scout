"""
异步令牌桶限速器。

参考：free-search-mcp 的 ratelimit.py 实现。
使用 asyncio.sleep() 实现异步等待，不依赖外部库。
"""

from __future__ import annotations

import asyncio
import time


class TokenBucket:
    """异步令牌桶。

    Args:
        rate_per_minute: 每分钟补充的令牌数。
        burst: 突发容量（默认等于 rate_per_minute）。
    """

    def __init__(self, rate_per_minute: float, burst: float | None = None) -> None:
        self.rate = rate_per_minute / 60.0  # 转换为每秒速率
        self.capacity = burst if burst is not None else rate_per_minute
        self.tokens = self.capacity
        self.last_refill = time.monotonic()

    async def acquire(self, n: int = 1) -> None:
        """获取 n 个令牌，如果不足则等待。"""
        while True:
            self._refill()
            if self.tokens >= n:
                self.tokens -= n
                return
            # 计算需要等待的时间
            deficit = n - self.tokens
            wait_time = deficit / self.rate
            await asyncio.sleep(wait_time)

    def _refill(self) -> None:
        """补充令牌。"""
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
        self.last_refill = now


class RateLimiter:
    """按 key 限速的限速器。

    每个 key 有独立的令牌桶，支持按引擎名称限速。
    """

    def __init__(self, default_rpm: float) -> None:
        self.default_rpm = default_rpm
        self._buckets: dict[str, TokenBucket] = {}

    def configure(self, key: str, rpm: float) -> None:
        """为指定 key 配置独立的限速。"""
        self._buckets[key] = TokenBucket(rpm)

    async def acquire(self, key: str) -> None:
        """获取指定 key 的令牌。"""
        bucket = self._buckets.get(key)
        if bucket is None:
            bucket = TokenBucket(self.default_rpm)
            self._buckets[key] = bucket
        await bucket.acquire()


# 全局限速器实例
_limiter: RateLimiter | None = None


def get_limiter() -> RateLimiter:
    """获取全局限速器实例（懒初始化）。"""
    global _limiter
    if _limiter is None:
        from .config import settings

        _limiter = RateLimiter(settings.rate_limit_per_minute)
    return _limiter
