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
    """SQLite + FTS5 缓存（同步版本）。"""

    def __init__(self, db_path: str | Path | None = None) -> None:
        if db_path is None:
            from .config import settings
            db_path = settings.cache_path()
        self._db_path = str(db_path)
        self._db: sqlite3.Connection | None = None

    def _get_db(self) -> sqlite3.Connection:
        """获取数据库连接（同步，懒初始化）。"""
        if self._db is None:
            self._db = sqlite3.connect(self._db_path)
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

    def _get_search_sync(self, cache_key: str, max_age_seconds: int) -> list[dict[str, Any]] | None:
        """同步获取搜索结果。"""
        db = self._get_db()
        cursor = db.execute("SELECT results, created FROM search_cache WHERE cache_key = ?", (cache_key,))
        row = cursor.fetchone()
        if row is None:
            return None
        results_json, created = row
        if time.time() - created > max_age_seconds:
            return None
        try:
            return json.loads(results_json)
        except json.JSONDecodeError:
            return None

    def _put_search_sync(self, cache_key: str, query: str, engines: list[str], results: list[dict[str, Any]]) -> None:
        """同步写入搜索结果。"""
        db = self._get_db()
        db.execute(
            "INSERT OR REPLACE INTO search_cache (cache_key, query, engines, results, created) VALUES (?, ?, ?, ?, ?)",
            (cache_key, query, json.dumps(engines, ensure_ascii=False), json.dumps(results, ensure_ascii=False), int(time.time())),
        )
        db.commit()

    def _get_page_sync(self, url: str, max_age_seconds: int) -> dict[str, Any] | None:
        """同步获取页面。"""
        db = self._get_db()
        cursor = db.execute("SELECT url, title, content, fetched FROM pages WHERE url = ?", (url,))
        row = cursor.fetchone()
        if row is None:
            return None
        url_, title, content, fetched = row
        if time.time() - fetched > max_age_seconds:
            return None
        return {"url": url_, "title": title, "content": content}

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
        db = self._get_db()
        try:
            cursor = db.execute(
                "SELECT url, title, snippet(pages_fts, 2, '[', ']', '...', 32) FROM pages_fts WHERE pages_fts MATCH ? ORDER BY rank LIMIT ?",
                (query, limit),
            )
            return [{"url": r[0], "title": r[1], "snippet": r[2]} for r in cursor.fetchall()]
        except Exception:
            return []

    # 异步接口（使用 asyncio.to_thread）
    async def initialize(self) -> None:
        await asyncio.to_thread(self._get_db)

    async def get_search(self, cache_key: str, max_age_seconds: int | None = None) -> list[dict[str, Any]] | None:
        from .config import settings
        if max_age_seconds is None:
            max_age_seconds = settings.cache_ttl_seconds
        return await asyncio.to_thread(self._get_search_sync, cache_key, max_age_seconds)

    async def put_search(self, cache_key: str, query: str, engines: list[str], results: list[dict[str, Any]]) -> None:
        await asyncio.to_thread(self._put_search_sync, cache_key, query, engines, results)

    async def get_page(self, url: str, max_age_seconds: int | None = None) -> dict[str, Any] | None:
        from .config import settings
        if max_age_seconds is None:
            max_age_seconds = settings.cache_ttl_seconds
        return await asyncio.to_thread(self._get_page_sync, url, max_age_seconds)

    async def put_page(self, url: str, title: str, content: str) -> None:
        await asyncio.to_thread(self._put_page_sync, url, title, content)

    async def search_pages(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self._search_pages_sync, query, limit)


# 全局缓存实例
cache = Cache()
