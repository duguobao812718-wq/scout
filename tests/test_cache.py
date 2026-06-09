"""缓存单元测试。"""

import asyncio
import os
import tempfile

import pytest

from src.cache import Cache


@pytest.fixture
def temp_cache():
    """创建临时缓存。"""
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as f:
        db_path = f.name

    cache = Cache(db_path)
    yield cache

    # 清理
    cache.close()
    if os.path.exists(db_path):
        os.unlink(db_path)


def test_make_cache_key():
    """测试缓存键生成。"""
    key1 = Cache.make_cache_key("test", ["bing"], 10)
    key2 = Cache.make_cache_key("test", ["bing"], 10)
    key3 = Cache.make_cache_key("other", ["bing"], 10)

    assert key1 == key2  # 相同参数生成相同键
    assert key1 != key3  # 不同参数生成不同键
    assert len(key1) == 64  # SHA-256 长度


def test_cache_init(temp_cache):
    """测试缓存初始化。"""
    db = temp_cache._get_db()
    assert db is not None

    # 检查表是否存在
    cursor = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='search_cache'"
    )
    assert cursor.fetchone() is not None


def test_search_cache(temp_cache):
    """测试搜索结果缓存。"""
    key = Cache.make_cache_key("test", ["bing"], 10)
    results = [{"title": "Test", "url": "https://example.com"}]

    # 写入
    temp_cache._put_search_sync(key, "test", ["bing"], results)

    # 读取
    cached = temp_cache._get_search_sync(key, max_age_seconds=3600)
    assert cached is not None
    assert len(cached) == 1
    assert cached[0]["title"] == "Test"

    # 过期
    cached = temp_cache._get_search_sync(key, max_age_seconds=0)
    assert cached is None


def test_page_cache(temp_cache):
    """测试页面缓存。"""
    url = "https://example.com"
    title = "Example"
    content = "This is example content"

    # 写入
    temp_cache._put_page_sync(url, title, content)

    # 读取
    cached = temp_cache._get_page_sync(url, max_age_seconds=3600)
    assert cached is not None
    assert cached["url"] == url
    assert cached["title"] == title
    assert cached["content"] == content


def test_search_pages(temp_cache):
    """测试全文搜索。"""
    # 写入页面
    temp_cache._put_page_sync(
        "https://example.com/1",
        "Python Tutorial",
        "Python is a programming language"
    )
    temp_cache._put_page_sync(
        "https://example.com/2",
        "Java Tutorial",
        "Java is a programming language"
    )

    # 搜索
    results = temp_cache._search_pages_sync("Python", limit=10)
    assert len(results) >= 1
    assert any("Python" in r.get("title", "") or "Python" in r.get("snippet", "") for r in results)
