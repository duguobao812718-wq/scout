"""
SQLite + FTS5 缓存层（同步版本，使用 asyncio.to_thread）。

避免 aiosqlite 的线程模型问题。
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger("scout.cache")

# SQL 建表语句
_SCHEMA = """
CREATE TABLE IF NOT EXISTS search_cache (
    cache_key TEXT PRIMARY KEY,
    query TEXT NOT NULL,
    engines TEXT NOT NULL,
    results TEXT NOT NULL,
    created INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS pages (
    url TEXT PRIMARY KEY,
    title TEXT,
    content TEXT NOT NULL,
    fetched INTEGER NOT NULL
);

CREATE VIRTUAL TABLE IF NOT EXISTS pages_fts USING fts5(
    url UNINDEXED, title, content,
    content='pages', content_rowid='rowid',
    tokenize='unicode61 remove_diacritics 2'
);

CREATE TRIGGER IF NOT EXISTS pages_ai AFTER INSERT ON pages BEGIN
    INSERT INTO pages_fts(rowid, url, title, content)
    VALUES (new.rowid, new.url, new.title, new.content);
END;

CREATE TRIGGER IF NOT EXISTS pages_ad AFTER DELETE ON pages BEGIN
    INSERT INTO pages_fts(pages_fts, rowid, url, title, content)
    VALUES ('delete', old.rowid, old.url, old.title, old.content);
END;

CREATE TRIGGER IF NOT EXISTS pages_au AFTER UPDATE ON pages BEGIN
    INSERT INTO pages_fts(pages_fts, rowid, url, title, content)
    VALUES ('delete', old.rowid, old.url, old.title, old.content);
    INSERT INTO pages_fts(rowid, url, title, content)
    VALUES (new.rowid, new.url, new.title, new.content);
END;
"""


class Cache:
    """SQLite + FTS5 缓存（同步版本）。

    改进特性：
    - 分层 TTL：搜索结果和页面可配置不同过期时间
    - Stale-while-revalidate：返回过期但未严重过期的缓存，后台刷新
    - 缓存清理：自动清理过期条目
    """

    def __init__(self, db_path: str | Path | None = None) -> None:
        if db_path is None:
            from .config import settings
            db_path = settings.cache_path()
        self._db_path = str(db_path)
        self._db: sqlite3.Connection | None = None
        self._lock = threading.Lock()

    def _get_db(self) -> sqlite3.Connection:
        """获取数据库连接（同步，懒初始化，线程安全）。"""
        if self._db is None:
            with self._lock:
                # 双重检查锁定
                if self._db is None:
                    self._db = sqlite3.connect(self._db_path, check_same_thread=False)
                    self._db.execute("PRAGMA journal_mode=WAL")
                    self._db.execute("PRAGMA busy_timeout=5000")
                    self._db.executescript(_SCHEMA)
                    self._db.commit()
                    logger.info("缓存数据库已初始化: %s", self._db_path)
        return self._db

    def close(self) -> None:
        """关闭数据库连接。"""
        if self._db:
            self._db.close()
            self._db = None

    @staticmethod
    def make_cache_key(
        query: str,
        engines: list[str],
        max_results: int,
        filters: dict[str, Any] | None = None,
    ) -> str:
        """生成缓存键。"""
        key_data = {"q": query, "e": sorted(engines), "n": max_results, "f": filters or {}}
        raw = json.dumps(key_data, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(raw.encode()).hexdigest()

    def _get_search_sync(
        self,
        cache_key: str,
        max_age_seconds: int,
        stale_age_seconds: int | None = None,
    ) -> tuple[list[dict[str, Any]] | None, bool]:
        """同步获取搜索结果。

        返回 (results, is_stale)。
        - (results, False): 新鲜缓存命中
        - (results, True): 过期但未严重过期（stale-while-revalidate）
        - (None, False): 缓存未命中
        """
        db = self._get_db()
        cursor = db.execute("SELECT results, created FROM search_cache WHERE cache_key = ?", (cache_key,))
        row = cursor.fetchone()
        if row is None:
            return None, False
        results_json, created = row
        age = time.time() - created

        if age <= max_age_seconds:
            # 新鲜缓存
            try:
                return json.loads(results_json), False
            except json.JSONDecodeError:
                return None, False

        # 检查是否在 stale 窗口内（默认 2x TTL）
        if stale_age_seconds is None:
            stale_age_seconds = max_age_seconds * 2
        if age <= stale_age_seconds:
            try:
                logger.debug("缓存 stale 命中 (age=%ds, max=%ds)", int(age), max_age_seconds)
                return json.loads(results_json), True
            except json.JSONDecodeError:
                return None, False

        return None, False

    def _put_search_sync(self, cache_key: str, query: str, engines: list[str], results: list[dict[str, Any]]) -> None:
        """同步写入搜索结果。"""
        db = self._get_db()
        db.execute(
            "INSERT OR REPLACE INTO search_cache (cache_key, query, engines, results, created) VALUES (?, ?, ?, ?, ?)",
            (cache_key, query, json.dumps(engines, ensure_ascii=False), json.dumps(results, ensure_ascii=False), int(time.time())),
        )
        db.commit()

    def _get_page_sync(
        self,
        url: str,
        max_age_seconds: int,
        stale_age_seconds: int | None = None,
    ) -> tuple[dict[str, Any] | None, bool]:
        """同步获取页面。

        返回 (page, is_stale)。
        """
        db = self._get_db()
        cursor = db.execute("SELECT url, title, content, fetched FROM pages WHERE url = ?", (url,))
        row = cursor.fetchone()
        if row is None:
            return None, False
        url_, title, content, fetched = row
        age = time.time() - fetched

        if age <= max_age_seconds:
            return {"url": url_, "title": title, "content": content}, False

        if stale_age_seconds is None:
            stale_age_seconds = max_age_seconds * 2
        if age <= stale_age_seconds:
            logger.debug("页面缓存 stale 命中 (age=%ds, max=%ds)", int(age), max_age_seconds)
            return {"url": url_, "title": title, "content": content}, True

        return None, False

    def _put_page_sync(self, url: str, title: str, content: str) -> None:
        """同步写入页面。"""
        db = self._get_db()
        db.execute(
            "INSERT OR REPLACE INTO pages (url, title, content, fetched) VALUES (?, ?, ?, ?)",
            (url, title, content, int(time.time())),
        )
        db.commit()

    def _search_pages_sync(self, query: str, limit: int) -> list[dict[str, Any]]:
        """同步全文搜索。"""
        import re as _re

        # FTS5 查询转义：用双引号包裹每个 token，防止特殊字符导致语法错误或性能问题
        safe_query = _re.sub(r'([*^"\'\-(){}[\]])', r'"\1"', query)
        # 如果转义后为空或只有特殊字符，用原始查询的双引号包裹
        if not safe_query.strip('"').strip():
            safe_query = f'"{query}"'

        db = self._get_db()
        try:
            cursor = db.execute(
                "SELECT url, title, snippet(pages_fts, 2, '[', ']', '...', 32) FROM pages_fts WHERE pages_fts MATCH ? ORDER BY rank LIMIT ?",
                (safe_query, limit),
            )
            return [{"url": r[0], "title": r[1], "snippet": r[2]} for r in cursor.fetchall()]
        except Exception:
            return []

    def _evict_sync(self, max_entries: int = 10000) -> int:
        """清理过期缓存条目。

        使用配置中的 cache_ttl_seconds 作为基准，删除超过 2x TTL 的条目。
        如果条目总数超过 max_entries，删除最旧的条目。
        返回清理的条目数。
        """
        from .config import settings

        db = self._get_db()
        now = int(time.time())
        ttl = settings.cache_ttl_seconds  # 使用配置的 TTL

        # 删除超过 2x TTL 的搜索缓存
        cursor = db.execute(
            "DELETE FROM search_cache WHERE created < ?",
            (now - ttl * 2,),
        )
        search_deleted = cursor.rowcount

        # 删除超过 2x TTL 的页面缓存
        cursor = db.execute(
            "DELETE FROM pages WHERE fetched < ?",
            (now - ttl * 2,),
        )
        page_deleted = cursor.rowcount

        # 如果条目总数仍超过 max_entries，删除最旧的条目
        total_count = db.execute("SELECT COUNT(*) FROM search_cache").fetchone()[0]
        if total_count > max_entries:
            excess = total_count - max_entries
            db.execute(
                "DELETE FROM search_cache WHERE cache_key IN "
                "(SELECT cache_key FROM search_cache ORDER BY created ASC LIMIT ?)",
                (excess,),
            )
            search_deleted += excess

        total_count = db.execute("SELECT COUNT(*) FROM pages").fetchone()[0]
        if total_count > max_entries:
            excess = total_count - max_entries
            db.execute(
                "DELETE FROM pages WHERE url IN "
                "(SELECT url FROM pages ORDER BY fetched ASC LIMIT ?)",
                (excess,),
            )
            page_deleted += excess

        db.commit()

        total = search_deleted + page_deleted
        if total > 0:
            logger.info("缓存清理: 删除 %d 条搜索缓存, %d 条页面缓存", search_deleted, page_deleted)
        return total

    def _stats_sync(self) -> dict[str, Any]:
        """获取缓存统计信息。"""
        db = self._get_db()
        search_count = db.execute("SELECT COUNT(*) FROM search_cache").fetchone()[0]
        page_count = db.execute("SELECT COUNT(*) FROM pages").fetchone()[0]
        return {
            "search_entries": search_count,
            "page_entries": page_count,
            "total_entries": search_count + page_count,
        }

    # 异步接口（使用 asyncio.to_thread）
    async def initialize(self) -> None:
        await asyncio.to_thread(self._get_db)

    async def get_search(
        self,
        cache_key: str,
        max_age_seconds: int | None = None,
    ) -> tuple[list[dict[str, Any]] | None, bool]:
        """获取搜索缓存，返回 (results, is_stale)。"""
        from .config import settings
        if max_age_seconds is None:
            max_age_seconds = settings.cache_ttl_seconds
        return await asyncio.to_thread(self._get_search_sync, cache_key, max_age_seconds)

    async def put_search(self, cache_key: str, query: str, engines: list[str], results: list[dict[str, Any]]) -> None:
        await asyncio.to_thread(self._put_search_sync, cache_key, query, engines, results)

    async def get_page(
        self,
        url: str,
        max_age_seconds: int | None = None,
    ) -> tuple[dict[str, Any] | None, bool]:
        """获取页面缓存，返回 (page, is_stale)。"""
        from .config import settings
        if max_age_seconds is None:
            max_age_seconds = settings.cache_ttl_seconds
        return await asyncio.to_thread(self._get_page_sync, url, max_age_seconds)

    async def put_page(self, url: str, title: str, content: str) -> None:
        await asyncio.to_thread(self._put_page_sync, url, title, content)

    async def search_pages(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self._search_pages_sync, query, limit)

    async def evict(self, max_entries: int = 10000) -> int:
        """清理过期缓存（异步）。"""
        return await asyncio.to_thread(self._evict_sync, max_entries)

    async def stats(self) -> dict[str, Any]:
        """获取缓存统计（异步）。"""
        return await asyncio.to_thread(self._stats_sync)


def create_cache() -> Cache | "RedisCache":
    """根据配置创建缓存实例。"""
    from .config import settings

    if settings.cache_backend == "redis":
        from .cache_redis import RedisCache
        logger.info("使用 Redis 缓存后端: %s", settings.redis_url)
        return RedisCache()
    else:
        logger.info("使用 SQLite 缓存后端")
        return Cache()


# 全局缓存实例
cache = create_cache()


# 类型别名，便于类型检查
try:
    from .cache_redis import RedisCache as _RedisCache
    CacheType = Cache | _RedisCache
except ImportError:
    CacheType = Cache
