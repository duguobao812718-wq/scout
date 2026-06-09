"""缓存单元测试。"""

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

    # 读取 - 新鲜缓存
    cached, is_stale = temp_cache._get_search_sync(key, max_age_seconds=3600)
    assert cached is not None
    assert is_stale is False
    assert len(cached) == 1
    assert cached[0]["title"] == "Test"

    # 过期（超过 max_age 但在 stale 窗口内）
    cached, is_stale = temp_cache._get_search_sync(key, max_age_seconds=0, stale_age_seconds=3600)
    assert cached is not None
    assert is_stale is True

    # 完全过期（超过 stale 窗口）
    cached, is_stale = temp_cache._get_search_sync(key, max_age_seconds=0, stale_age_seconds=0)
    assert cached is None
    assert is_stale is False


def test_page_cache(temp_cache):
    """测试页面缓存。"""
    url = "https://example.com"
    title = "Example"
    content = "This is example content"

    # 写入
    temp_cache._put_page_sync(url, title, content)

    # 读取 - 新鲜缓存
    cached, is_stale = temp_cache._get_page_sync(url, max_age_seconds=3600)
    assert cached is not None
    assert is_stale is False
    assert cached["url"] == url
    assert cached["title"] == title
    assert cached["content"] == content

    # stale 缓存
    cached, is_stale = temp_cache._get_page_sync(url, max_age_seconds=0, stale_age_seconds=3600)
    assert cached is not None
    assert is_stale is True


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


def test_cache_evict(temp_cache):
    """测试缓存清理。"""
    key = Cache.make_cache_key("test", ["bing"], 10)
    results = [{"title": "Test", "url": "https://example.com"}]
    temp_cache._put_search_sync(key, "test", ["bing"], results)
    temp_cache._put_page_sync("https://example.com", "Test", "content")

    # 清理（max_entries 很大，不会清理新数据）
    deleted = temp_cache._evict_sync(max_entries=10000)
    assert deleted == 0  # 新数据不应被清理

    # 验证数据仍在
    cached, _ = temp_cache._get_search_sync(key, max_age_seconds=3600)
    assert cached is not None


def test_cache_stats(temp_cache):
    """测试缓存统计。"""
    # 写入数据
    key = Cache.make_cache_key("test", ["bing"], 10)
    temp_cache._put_search_sync(key, "test", ["bing"], [{"title": "Test"}])
    temp_cache._put_page_sync("https://example.com", "Test", "content")

    stats = temp_cache._stats_sync()
    assert stats["search_entries"] == 1
    assert stats["page_entries"] == 1
    assert stats["total_entries"] == 2


def test_dedup_url_normalization():
    """测试 URL 归一化去重逻辑。"""
    from src.utils import normalize_url, title_similarity

    # 追踪参数去除
    assert normalize_url("https://example.com/page?utm_source=google&id=1") == \
           normalize_url("https://example.com/page?id=1&utm_source=bing")

    # www 前缀去除
    assert normalize_url("https://www.example.com/page") == \
           normalize_url("https://example.com/page")

    # 尾部斜杠去除
    assert normalize_url("https://example.com/page/") == \
           normalize_url("https://example.com/page")

    # 不同页面不去重
    assert normalize_url("https://example.com/page1") != \
           normalize_url("https://example.com/page2")

    # 标题相似度
    assert title_similarity("Python Tutorial", "Python Tutorial Guide") > 0.8
    assert title_similarity("Python Tutorial", "Java Programming") < 0.5
    assert title_similarity("", "") == 0.0
