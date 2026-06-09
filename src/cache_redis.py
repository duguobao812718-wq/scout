"""
Redis 缓存后端。

与 SQLite 缓存相同的异步接口，用于多实例共享缓存场景。
需要安装: pip install redis[hiredis]
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

logger = logging.getLogger("scout.cache.redis")


class RedisCache:
    """Redis 缓存后端。

    接口与 Cache 类一致，可直接替换。
    使用 Redis 的 TTL 自动过期，无需手动清理。
    """

    def __init__(self, redis_url: str | None = None) -> None:
        if redis_url is None:
            from .config import settings
            redis_url = settings.redis_url
        self._redis_url = redis_url
        self._redis = None

    async def _get_redis(self):
        """获取 Redis 连接（懒初始化）。"""
        if self._redis is None:
            try:
                import redis.asyncio as aioredis
                self._redis = aioredis.from_url(
                    self._redis_url,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5,
                )
                # 测试连接
                await self._redis.ping()
                logger.info("Redis 缓存已连接: %s", self._redis_url)
            except ImportError:
                raise ImportError("Redis 缓存需要安装: pip install redis[hiredis]")
            except Exception as e:
                logger.error("Redis 连接失败: %s", e)
                raise
        return self._redis

    def close(self) -> None:
        """关闭 Redis 连接。"""
        if self._redis:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.ensure_future(self._redis.close())
                else:
                    loop.run_until_complete(self._redis.close())
            except Exception:
                pass
            self._redis = None

    @staticmethod
    def make_cache_key(
        query: str,
        engines: list[str],
        max_results: int,
        filters: dict[str, Any] | None = None,
    ) -> str:
        """生成缓存键（与 SQLite 版本一致）。"""
        import hashlib
        key_data = {"q": query, "e": sorted(engines), "n": max_results, "f": filters or {}}
        raw = json.dumps(key_data, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(raw.encode()).hexdigest()

    async def get_search(
        self,
        cache_key: str,
        max_age_seconds: int | None = None,
    ) -> tuple[list[dict[str, Any]] | None, bool]:
        """获取搜索缓存。"""
        from .config import settings
        if max_age_seconds is None:
            max_age_seconds = settings.cache_ttl_seconds

        r = await self._get_redis()
        data = await r.get(f"scout:search:{cache_key}")
        if data is None:
            return None, False

        try:
            entry = json.loads(data)
        except json.JSONDecodeError:
            return None, False

        age = time.time() - entry.get("created", 0)
        is_stale = age > max_age_seconds
        return entry.get("results"), is_stale

    async def put_search(
        self,
        cache_key: str,
        query: str,
        engines: list[str],
        results: list[dict[str, Any]],
    ) -> None:
        """写入搜索缓存。"""
        from .config import settings
        r = await self._get_redis()

        entry = json.dumps({
            "results": results,
            "query": query,
            "engines": engines,
            "created": int(time.time()),
        }, ensure_ascii=False)

        # 设置 TTL 为 2x cache_ttl（stale 窗口）
        ttl = settings.cache_ttl_seconds * 2
        await r.setex(f"scout:search:{cache_key}", ttl, entry)

    async def get_page(
        self,
        url: str,
        max_age_seconds: int | None = None,
    ) -> tuple[dict[str, Any] | None, bool]:
        """获取页面缓存。"""
        from .config import settings
        if max_age_seconds is None:
            max_age_seconds = settings.cache_ttl_seconds

        r = await self._get_redis()
        data = await r.get(f"scout:page:{url}")
        if data is None:
            return None, False

        try:
            entry = json.loads(data)
        except json.JSONDecodeError:
            return None, False

        age = time.time() - entry.get("fetched", 0)
        is_stale = age > max_age_seconds
        return {
            "url": entry.get("url", url),
            "title": entry.get("title", ""),
            "content": entry.get("content", ""),
        }, is_stale

    async def put_page(self, url: str, title: str, content: str) -> None:
        """写入页面缓存。"""
        from .config import settings
        r = await self._get_redis()

        entry = json.dumps({
            "url": url,
            "title": title,
            "content": content,
            "fetched": int(time.time()),
        }, ensure_ascii=False)

        ttl = settings.cache_ttl_seconds * 2
        await r.setex(f"scout:page:{url}", ttl, entry)

    async def search_pages(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """全文搜索已缓存页面（Redis 不原生支持 FTS5，使用 SCAN + 简单匹配）。"""
        r = await self._get_redis()
        results = []
        query_lower = query.lower()

        # SCAN 遍历所有页面键
        cursor = 0
        while True:
            cursor, keys = await r.scan(cursor, match="scout:page:*", count=100)
            for key in keys:
                data = await r.get(key)
                if data is None:
                    continue
                try:
                    entry = json.loads(data)
                except json.JSONDecodeError:
                    continue

                title = entry.get("title", "")
                content = entry.get("content", "")
                url = entry.get("url", "")

                # 简单关键词匹配
                if query_lower in title.lower() or query_lower in content.lower():
                    # 生成摘要片段
                    snippet = ""
                    idx = content.lower().find(query_lower)
                    if idx >= 0:
                        start = max(0, idx - 50)
                        end = min(len(content), idx + len(query) + 50)
                        snippet = content[start:end]

                    results.append({
                        "url": url,
                        "title": title,
                        "snippet": snippet,
                    })

                if len(results) >= limit:
                    break

            if len(results) >= limit or cursor == 0:
                break

        return results[:limit]

    async def evict(self, max_entries: int = 10000) -> int:
        """清理过期缓存（Redis 自动通过 TTL 清理，此方法用于手动清理）。"""
        r = await self._get_redis()
        deleted = 0

        # 清理搜索缓存
        cursor = 0
        while True:
            cursor, keys = await r.scan(cursor, match="scout:search:*", count=100)
            if keys:
                deleted += await r.delete(*keys)
            if cursor == 0:
                break

        # 清理页面缓存
        cursor = 0
        while True:
            cursor, keys = await r.scan(cursor, match="scout:page:*", count=100)
            if keys:
                deleted += await r.delete(*keys)
            if cursor == 0:
                break

        if deleted > 0:
            logger.info("Redis 缓存清理: 删除 %d 条", deleted)
        return deleted

    async def stats(self) -> dict[str, Any]:
        """获取缓存统计信息。"""
        r = await self._get_redis()

        search_count = 0
        cursor = 0
        while True:
            cursor, keys = await r.scan(cursor, match="scout:search:*", count=1000)
            search_count += len(keys)
            if cursor == 0:
                break

        page_count = 0
        cursor = 0
        while True:
            cursor, keys = await r.scan(cursor, match="scout:page:*", count=1000)
            page_count += len(keys)
            if cursor == 0:
                break

        info = await r.info("memory")

        return {
            "search_entries": search_count,
            "page_entries": page_count,
            "total_entries": search_count + page_count,
            "redis_memory_used": info.get("used_memory_human", "unknown"),
            "redis_connected_clients": info.get("connected_clients", 0),
        }

    async def initialize(self) -> None:
        """初始化 Redis 连接。"""
        await self._get_redis()
