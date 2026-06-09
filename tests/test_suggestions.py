"""搜索建议模块测试。"""

import pytest

from src.suggestions import (
    extract_related_searches,
    extract_spell_correction,
    rewrite_query,
)


# ── 相关搜索提取测试 ──────────────────────────────────────


class TestExtractRelatedSearches:
    def test_google_related(self):
        html = '''
        <div>
            <a href="/search?q=python+tutorial+beginner">python tutorial beginner</a>
            <a href="/search?q=python+programming+language">python programming language</a>
            <a href="/search?q=learn+python+free">learn python free</a>
        </div>
        '''
        related = extract_related_searches(html, "google")
        assert len(related) > 0

    def test_bing_related(self):
        html = '''
        <div>
            <a href="/search?q=python+docs" class="related_search">python docs</a>
            <a href="/search?q=python+download" class="related_search">python download</a>
        </div>
        '''
        related = extract_related_searches(html, "bing")
        assert len(related) > 0

    def test_empty_html(self):
        related = extract_related_searches("<html><body></body></html>", "google")
        assert related == []

    def test_deduplication(self):
        html = '''
        <a href="/search?q=python">Python</a>
        <a href="/search?q=python">python</a>
        '''
        related = extract_related_searches(html, "google")
        # 去重后应只有一个
        lower_related = [r.lower() for r in related]
        assert lower_related.count("python") <= 1

    def test_max_results(self):
        # 生成 20 个相关搜索
        links = "\n".join([
            f'<a href="/search?q=term{i}">term{i}</a>'
            for i in range(20)
        ])
        related = extract_related_searches(links, "google")
        assert len(related) <= 10


# ── 拼写纠错测试 ──────────────────────────────────────────


class TestExtractSpellCorrection:
    def test_google_did_you_mean(self):
        html = 'Did you mean: <a href="/search?q=python">python</a>'
        correction = extract_spell_correction(html, "google")
        assert correction == "python"

    def test_google_showing_results_for(self):
        html = 'Showing results for <a href="/search?q=python">python</a>'
        correction = extract_spell_correction(html, "google")
        assert correction == "python"

    def test_no_correction(self):
        html = '<html><body>Normal search results</body></html>'
        correction = extract_spell_correction(html, "google")
        assert correction is None

    def test_bing_correction(self):
        html = 'Did you mean: <a href="/search?q=python">python</a>'
        correction = extract_spell_correction(html, "bing")
        assert correction == "python"


# ── 查询改写测试 ──────────────────────────────────────────


class TestRewriteQuery:
    def test_add_quotes(self):
        suggestions = rewrite_query("python tutorial")
        assert any('"' in s for s in suggestions)

    def test_normalize_spaces(self):
        suggestions = rewrite_query("python   tutorial   guide")
        assert any("python tutorial guide" == s for s in suggestions)

    def test_shorten_long_query(self):
        long_query = "how to learn python programming for beginners step by step guide"
        suggestions = rewrite_query(long_query)
        assert any(len(s.split()) < len(long_query.split()) for s in suggestions)

    def test_empty_query(self):
        suggestions = rewrite_query("")
        assert suggestions == []

    def test_single_word_no_quotes(self):
        suggestions = rewrite_query("python")
        # 单词不应添加引号
        assert not any('"' in s for s in suggestions if s == '"python"')

    def test_already_has_quotes(self):
        suggestions = rewrite_query('"python tutorial"')
        # 已有引号不应再添加
        assert len(suggestions) <= 1  # 可能有空格归一化

    def test_max_suggestions(self):
        suggestions = rewrite_query("a  very   long    query     with      many        words")
        assert len(suggestions) <= 3
