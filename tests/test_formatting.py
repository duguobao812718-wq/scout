"""格式化单元测试。"""

from src.formatting import (
    errors_to_hint,
    estimate_tokens,
    render_fetch,
    render_search,
    render_structured,
    smart_truncate,
)


def test_estimate_tokens_empty():
    """测试空文本 token 估算。"""
    assert estimate_tokens("") == 0
    assert estimate_tokens(None) == 0


def test_estimate_tokens_english():
    """测试英文 token 估算。"""
    # 英文：4 字符 ≈ 1 token
    assert estimate_tokens("test") == 1  # 4 字符 → 1 token
    assert estimate_tokens("hello world") == 3  # 10 字符 → 3 token


def test_estimate_tokens_cjk():
    """测试中文 token 估算。"""
    # 中文：1 字符 ≈ 1 token
    assert estimate_tokens("测试") == 2
    assert estimate_tokens("你好世界") == 4


def test_smart_truncate_short():
    """测试短文本截断。"""
    text = "Hello World"
    assert smart_truncate(text, 100) == text


def test_smart_truncate_long():
    """测试长文本截断。"""
    text = "A" * 1000
    result = smart_truncate(text, 100)
    assert len(result) <= 100


def test_smart_truncate_paragraph():
    """测试段落边界截断。"""
    text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
    result = smart_truncate(text, 30)
    assert "First paragraph." in result


def test_errors_to_hint_empty():
    """测试空错误提示。"""
    assert errors_to_hint(None) == ""
    assert errors_to_hint({}) == ""


def test_errors_to_hint_with_errors():
    """测试错误提示。"""
    errors = {"bing": "timeout", "brave": "blocked"}
    hint = errors_to_hint(errors)
    assert "bing" in hint
    assert "brave" in hint


def test_render_search_empty():
    """测试空搜索结果渲染。"""
    payload = {"results": []}
    result = render_search(payload)
    assert "未找到结果" in result


def test_render_search_with_results():
    """测试搜索结果渲染。"""
    payload = {
        "query": "test",
        "engines": ["bing"],
        "results": [
            {
                "title": "Test",
                "url": "https://example.com",
                "snippet": "Test snippet",
                "engines": ["bing"],
                "score": 0.5,
            }
        ],
        "cached": False,
    }
    result = render_search(payload)
    assert "Test" in result
    assert "https://example.com" in result


def test_render_fetch():
    """测试抓取结果渲染。"""
    result = {
        "url": "https://example.com",
        "title": "Example",
        "content": "Hello World",
        "method": "http",
        "truncated": False,
        "tokens_estimated": 2,
    }
    output = render_fetch(result)
    assert "Example" in output
    assert "Hello World" in output


def test_render_structured():
    """测试结构化数据渲染。"""
    payload = {
        "url": "https://example.com",
        "json_ld": [{"@type": "WebSite"}],
        "opengraph": {"title": "Example"},
        "twitter_card": {},
        "microdata": [],
    }
    output = render_structured(payload)
    assert "JSON-LD" in output
    assert "OpenGraph" in output
