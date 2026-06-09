"""搜索引擎单元测试。"""

import pytest

from src.engines import SearchFilters, SearchResult, get_engine, list_engines


def test_list_engines():
    """测试引擎列表。"""
    engines = list_engines()
    assert "bing" in engines
    assert "brave" in engines
    assert "google" in engines
    assert "duckduckgo" in engines
    assert len(engines) >= 4


def test_get_engine():
    """测试获取引擎。"""
    engine = get_engine("bing")
    assert engine.name == "bing"

    with pytest.raises(ValueError, match="未知引擎"):
        get_engine("nonexistent")


def test_search_filters():
    """测试搜索过滤器。"""
    filters = SearchFilters(
        freshness="week",
        include_domains=["python.org"],
        exclude_domains=["example.com"],
    )
    assert filters.freshness == "week"
    assert "python.org" in filters.include_domains
    assert "example.com" in filters.exclude_domains


def test_search_result():
    """测试搜索结果。"""
    result = SearchResult(
        title="Test",
        url="https://example.com",
        snippet="Test snippet",
        engine="bing",
        rank=1,
    )
    assert result.title == "Test"
    assert result.url == "https://example.com"
    assert result.engine == "bing"


def test_bing_build_url():
    """测试 Bing 引擎 URL 构建。"""
    engine = get_engine("bing")
    url = engine.build_url("Python tutorial", 10)

    assert "bing.com/search" in url
    assert "q=Python+tutorial" in url or "q=Python%20tutorial" in url
    assert "format=rss" in url


def test_brave_build_url():
    """测试 Brave 引擎 URL 构建。"""
    engine = get_engine("brave")
    url = engine.build_url("Python tutorial", 10)

    assert "search.brave.com" in url
    assert "q=Python" in url


def test_google_build_url():
    """测试 Google 引擎 URL 构建。"""
    engine = get_engine("google")
    url = engine.build_url("Python tutorial", 10)

    assert "google.com/search" in url
    assert "q=Python" in url


def test_duckduckgo_build_url():
    """测试 DuckDuckGo 引擎 URL 构建。"""
    engine = get_engine("duckduckgo")
    url = engine.build_url("Python tutorial", 10)

    assert "duckduckgo.com" in url
    assert "q=Python" in url
