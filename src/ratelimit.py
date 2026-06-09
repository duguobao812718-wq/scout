"""
异步令牌桶限速器 + 熔断器。

参考：free-search-mcp 的 ratelimit.py 实现。
使用 asyncio.sleep() 实现异步等待，不依赖外部库。
"""

from __future__ import annotations

import asyncio
import logging
import time

logger = logging.getLogger("scout.ratelimit")


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


class CircuitBreaker:
    """熔断器。

    当连续失败次数超过阈值时，熔断器打开，暂停该引擎一段时间。

    Args:
        failure_threshold: 触发熔断的连续失败次数。
        recovery_timeout: 熔断恢复时间（秒）。
    """

    def __init__(self, failure_threshold: int = 3, recovery_timeout: float = 60.0) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = 0.0
        self.state = "closed"  # closed (正常) / open (熔断) / half-open (试探)

    def record_success(self) -> None:
        """记录成功调用，重置熔断器。"""
        self.failure_count = 0
        self.state = "closed"

    def record_failure(self) -> None:
        """记录失败调用。"""
        self.failure_count += 1
        self.last_failure_time = time.monotonic()
        if self.failure_count >= self.failure_threshold:
            self.state = "open"
            logger.warning("熔断器打开: 连续 %d 次失败，暂停 %.0f 秒", self.failure_count, self.recovery_timeout)

    def is_available(self) -> bool:
        """检查是否可用。"""
        if self.state == "closed":
            return True
        if self.state == "open":
            # 检查是否超过恢复时间
            if time.monotonic() - self.last_failure_time >= self.recovery_timeout:
                self.state = "half-open"
                return True
            return False
        # half-open 状态，允许试探
        return True


class RateLimiter:
    """按 key 限速的限速器 + 熔断器。

    每个 key 有独立的令牌桶和熔断器，支持按引擎名称限速。
    """

    def __init__(self, default_rpm: float) -> None:
        self.default_rpm = default_rpm
        self._buckets: dict[str, TokenBucket] = {}
        self._breakers: dict[str, CircuitBreaker] = {}

    def configure(self, key: str, rpm: float) -> None:
        """为指定 key 配置独立的限速。"""
        self._buckets[key] = TokenBucket(rpm)

    async def acquire(self, key: str) -> None:
        """获取指定 key 的令牌（检查熔断状态）。"""
        # 检查熔断器
        breaker = self._breakers.get(key)
        if breaker and not breaker.is_available():
            raise CircuitOpenError(f"引擎 {key} 已熔断，请稍后重试")

        bucket = self._buckets.get(key)
        if bucket is None:
            bucket = TokenBucket(self.default_rpm)
            self._buckets[key] = bucket
        await bucket.acquire()

    def record_success(self, key: str) -> None:
        """记录指定 key 的成功调用。"""
        if key not in self._breakers:
            self._breakers[key] = CircuitBreaker()
        self._breakers[key].record_success()

    def record_failure(self, key: str) -> None:
        """记录指定 key 的失败调用。"""
        if key not in self._breakers:
            self._breakers[key] = CircuitBreaker()
        self._breakers[key].record_failure()

    def get_breaker(self, key: str) -> CircuitBreaker:
        """获取指定 key 的熔断器。"""
        if key not in self._breakers:
            self._breakers[key] = CircuitBreaker()
        return self._breakers[key]


class CircuitOpenError(Exception):
    """熔断器打开时抛出的异常。"""
    pass


# 全局限速器实例
_limiter: RateLimiter | None = None


def get_limiter() -> RateLimiter:
    """获取全局限速器实例（懒初始化）。"""
    global _limiter
    if _limiter is None:
        from .config import settings

        _limiter = RateLimiter(settings.rate_limit_per_minute)
    return _limiter
