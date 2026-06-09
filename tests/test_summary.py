"""结果摘要模块测试。"""

import pytest

from src.summary import (
    compute_credibility,
    extract_key_points,
    format_summary_for_agent,
)


# ── 关键要点提取测试 ──────────────────────────────────────


class TestExtractKeyPoints:
    def test_basic_extraction(self):
        content = "Python 是一种广泛使用的高级编程语言。它由 Guido van Rossum 创建。Python 支持多种编程范式。"
        points = extract_key_points(content, max_points=3)
        assert len(points) > 0
        assert len(points) <= 3

    def test_empty_content(self):
        assert extract_key_points("") == []

    def test_short_sentences_filtered(self):
        content = "短。这是一个足够长的句子，应该被提取出来作为关键要点。"
        points = extract_key_points(content)
        for p in points:
            assert len(p) >= 10

    def test_numbers_boosted(self):
        content = "Python 拥有超过 1000 万个开发者。Python 是一种编程语言。全球有 50% 的开发者使用 Python。"
        points = extract_key_points(content, max_points=2)
        # 包含数字的句子应该排在前面
        assert any("1000" in p or "50%" in p for p in points)

    def test_definition_boosted(self):
        content = "机器学习是人工智能的一个子领域。天气很好。深度学习是指多层神经网络。"
        points = extract_key_points(content, max_points=2)
        assert any("是" in p or "是指" in p for p in points)

    def test_max_points_respected(self):
        content = "。".join([f"这是一个测试句子 number {i}" for i in range(20)])
        points = extract_key_points(content, max_points=3)
        assert len(points) <= 3


# ── 可信度评估测试 ────────────────────────────────────────


class TestComputeCredibility:
    def test_no_sources(self):
        result = compute_credibility([])
        assert result["score"] == 0.0
        assert result["level"] == "low"

    def test_single_source(self):
        sources = [{"url": "https://example.com/page", "engines": ["bing"]}]
        result = compute_credibility(sources)
        assert 0.0 < result["score"] < 1.0
        assert result["level"] in ("low", "medium", "high")

    def test_multiple_sources_higher_score(self):
        sources = [
            {"url": "https://example1.com/page", "engines": ["bing"]},
            {"url": "https://example2.com/page", "engines": ["google"]},
            {"url": "https://example3.com/page", "engines": ["brave"]},
        ]
        result = compute_credibility(sources)
        assert result["score"] > 0.3

    def test_trusted_domains_boost(self):
        sources = [
            {"url": "https://docs.python.org/3/tutorial", "engines": ["bing", "google"]},
            {"url": "https://stackoverflow.com/questions/123", "engines": ["bing"]},
        ]
        result = compute_credibility(sources)
        assert result["factors"]["avg_domain_reputation"] > 0

    def test_multi_engine_boost(self):
        sources = [
            {"url": "https://example.com/page", "engines": ["bing", "google", "brave"]},
        ]
        result = compute_credibility(sources)
        assert result["factors"]["multi_engine_sources"] == 1

    def test_diverse_domains(self):
        sources = [
            {"url": "https://a.com/page", "engines": ["bing"]},
            {"url": "https://b.com/page", "engines": ["google"]},
            {"url": "https://c.com/page", "engines": ["brave"]},
        ]
        result = compute_credibility(sources)
        assert result["factors"]["unique_domains"] == 3

    def test_score_bounded(self):
        # 极端情况也应有界
        sources = [
            {"url": f"https://site{i}.com/page", "engines": ["bing", "google", "brave"]}
            for i in range(20)
        ]
        result = compute_credibility(sources)
        assert 0.0 <= result["score"] <= 1.0


# ── 格式化测试 ────────────────────────────────────────────


class TestFormatSummary:
    def test_basic_format(self):
        sources = [
            {"title": "Python.org", "url": "https://python.org", "engines": ["bing"]},
        ]
        result = format_summary_for_agent("What is Python?", sources)
        assert "Python" in result
        assert "python.org" in result

    def test_with_documents(self):
        sources = [
            {"title": "Python.org", "url": "https://python.org", "engines": ["bing"]},
        ]
        documents = [
            {
                "title": "Python.org",
                "url": "https://python.org",
                "content": "Python 是一种广泛使用的高级编程语言。它由 Guido van Rossum 在 1991 年创建。Python 支持多种编程范式，包括面向对象、命令式和函数式编程。",
            },
        ]
        result = format_summary_for_agent("What is Python?", sources, documents)
        assert "关键要点" in result

    def test_credibility_in_output(self):
        sources = [
            {"title": "Page 1", "url": "https://a.com/page", "engines": ["bing"]},
            {"title": "Page 2", "url": "https://b.com/page", "engines": ["google"]},
        ]
        result = format_summary_for_agent("test", sources)
        assert "可信度" in result
