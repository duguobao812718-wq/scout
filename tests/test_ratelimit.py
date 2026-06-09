"""限速器单元测试。"""

import asyncio
import time

import pytest

from src.ratelimit import TokenBucket, RateLimiter


def test_token_bucket_init():
    """测试令牌桶初始化。"""
    bucket = TokenBucket(60)  # 每分钟 60 个
    assert bucket.rate == 1.0  # 每秒 1 个
    assert bucket.capacity == 60
    assert bucket.tokens == 60


def test_token_bucket_acquire():
    """测试令牌获取。"""
    bucket = TokenBucket(60)

    # 获取令牌
    asyncio.run(bucket.acquire(1))
    assert bucket.tokens < 60


def test_token_bucket_refill():
    """测试令牌补充。"""
    bucket = TokenBucket(60)
    bucket.tokens = 0
    bucket.last_refill = time.monotonic() - 1  # 1 秒前

    bucket._refill()
    assert bucket.tokens > 0


def test_rate_limiter_init():
    """测试限速器初始化。"""
    limiter = RateLimiter(60)
    assert limiter.default_rpm == 60


def test_rate_limiter_configure():
    """测试限速器配置。"""
    limiter = RateLimiter(60)
    limiter.configure("bing", 120)

    assert "bing" in limiter._buckets
    assert limiter._buckets["bing"].rate == 2.0


def test_rate_limiter_acquire():
    """测试限速器获取令牌。"""
    limiter = RateLimiter(60)

    # 获取令牌
    asyncio.run(limiter.acquire("bing"))
    assert "bing" in limiter._buckets
