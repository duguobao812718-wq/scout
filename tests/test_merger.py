"""RRF 合并算法单元测试。"""

import pytest

from src.engines import SearchResult
from src.server import _merge_rrf


def _make_result(title: str, url: str, snippet: str = "", engine: str = "test", published_age: str = "") -> SearchResult:
    """构造测试用搜索结果。"""
    return SearchResult(title=title, url=url, snippet=snippet, engine=engine, published_age=published_age)


class TestMergeRRF:
    """RRF 合并测试。"""

    def test_basic_merge(self):
        """单引擎结果直接按排名返回。"""
        results = {
            "bing": [
                _make_result("A", "https://a.com", "snippet a"),
                _make_result("B", "https://b.com", "snippet b"),
            ]
        }
        merged = _merge_rrf(results, max_results=10)
        assert len(merged) == 2
        assert merged[0]["url"] == "https://a.com"
        assert merged[1]["url"] == "https://b.com"
        assert merged[0]["engines"] == ["bing"]

    def test_cross_engine_dedup(self):
        """跨引擎相同 URL 应合并，分数叠加。"""
        results = {
            "bing": [_make_result("A", "https://a.com", "from bing")],
            "duckduckgo": [_make_result("A", "https://a.com", "from ddg")],
        }
        merged = _merge_rrf(results, max_results=10)
        assert len(merged) == 1
        assert set(merged[0]["engines"]) == {"bing", "duckduckgo"}
        # 保留最长摘要
        assert merged[0]["snippet"] == "from bing"  # 一样长保留第一个

    def test_normalized_url_dedup(self):
        """归一化后相同的 URL 应合并。"""
        results = {
            "bing": [_make_result("A", "https://www.example.com/page?utm_source=google")],
            "duckduckgo": [_make_result("A", "https://example.com/page/")],
        }
        merged = _merge_rrf(results, max_results=10)
        assert len(merged) == 1
        assert set(merged[0]["engines"]) == {"bing", "duckduckgo"}

    def test_title_similarity_dedup(self):
        """同域名下高度相似的标题应去重。"""
        results = {
            "bing": [
                _make_result("Python Tutorial", "https://example.com/a"),
                _make_result("Python Tutorial Guide", "https://example.com/b"),
            ]
        }
        merged = _merge_rrf(results, max_results=10)
        # 标题相似度 > 0.8，应只保留一个
        assert len(merged) == 1

    def test_different_domains_not_deduped(self):
        """不同域名的相似标题不应去重。"""
        results = {
            "bing": [
                _make_result("Python Tutorial", "https://a.com/page"),
                _make_result("Python Tutorial", "https://b.com/page"),
            ]
        }
        merged = _merge_rrf(results, max_results=10)
        assert len(merged) == 2

    def test_max_results_limit(self):
        """结果数不超过 max_results。"""
        results = {
            "bing": [_make_result(f"R{i}", f"https://{i}.com") for i in range(20)]
        }
        merged = _merge_rrf(results, max_results=5)
        assert len(merged) == 5

    def test_empty_results(self):
        """空输入返回空列表。"""
        assert _merge_rrf({}, max_results=10) == []
        assert _merge_rrf({"bing": []}, max_results=10) == []

    def test_rrf_scoring(self):
        """多引擎出现的 URL 应排名更高。"""
        results = {
            "bing": [
                _make_result("Common", "https://common.com"),  # rank 1
                _make_result("Bing only", "https://bing.com"),  # rank 2
            ],
            "duckduckgo": [
                _make_result("DDG only", "https://ddg.com"),  # rank 1
                _make_result("Common", "https://common.com"),  # rank 2
            ],
        }
        merged = _merge_rrf(results, max_results=10)
        # common.com 在两个引擎都出现，分数应最高
        assert merged[0]["url"] == "https://common.com"

    def test_snippet_keeps_longest(self):
        """合并时保留最长摘要。"""
        results = {
            "bing": [_make_result("A", "https://a.com", "short")],
            "duckduckgo": [_make_result("A", "https://a.com", "this is a much longer snippet")],
        }
        merged = _merge_rrf(results, max_results=10)
        assert merged[0]["snippet"] == "this is a much longer snippet"

    def test_title_keeps_longest(self):
        """合并时保留更详细的标题。"""
        results = {
            "bing": [_make_result("A", "https://a.com")],
            "duckduckgo": [_make_result("A - Full Title", "https://a.com")],
        }
        merged = _merge_rrf(results, max_results=10)
        assert merged[0]["title"] == "A - Full Title"

    def test_published_age_preserved(self):
        """保留日期提示。"""
        results = {
            "bing": [_make_result("A", "https://a.com", published_age="2 days ago")]
        }
        merged = _merge_rrf(results, max_results=10)
        assert merged[0]["published_age"] == "2 days ago"
