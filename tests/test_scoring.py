"""结果评分模块测试。"""


from src.scoring import (
    compute_quality_bonus,
    domain_reputation_score,
    freshness_score,
    multi_engine_score,
    page_quality_score,
)

# ── 域名信誉测试 ──────────────────────────────────────────


class TestDomainReputation:
    def test_whitelist_domain(self):
        score = domain_reputation_score("https://docs.python.org/3/tutorial")
        assert score > 0

    def test_blacklist_domain(self):
        score = domain_reputation_score("https://www.pinterest.com/pin/123")
        assert score < 0

    def test_unknown_domain(self):
        score = domain_reputation_score("https://random-blog.example.com/post")
        assert score == 0.0

    def test_subdomain_whitelist(self):
        # github.com 子域名也应匹配
        score = domain_reputation_score("https://gist.github.com/user/123")
        assert score > 0

    def test_subdomain_blacklist(self):
        score = domain_reputation_score("https://sub.quora.com/answer")
        assert score < 0

    def test_stackoverflow(self):
        score = domain_reputation_score("https://stackoverflow.com/questions/12345")
        assert score > 0

    def test_medium_low_boost(self):
        score = domain_reputation_score("https://medium.com/@user/post")
        assert score > 0
        assert score < 0.05  # Medium 信誉不高

    def test_invalid_url(self):
        score = domain_reputation_score("not a url")
        assert score == 0.0

    def test_empty_url(self):
        score = domain_reputation_score("")
        assert score == 0.0


# ── 新鲜度加权测试 ────────────────────────────────────────


class TestFreshnessScore:
    def test_minutes_ago(self):
        assert freshness_score("5 minutes ago") == 0.10

    def test_hours_ago(self):
        assert freshness_score("3 hours ago") == 0.10

    def test_days_ago(self):
        assert freshness_score("2 days ago") == 0.08

    def test_weeks_ago(self):
        assert freshness_score("1 week ago") == 0.05

    def test_months_ago(self):
        assert freshness_score("3 months ago") == 0.03

    def test_years_ago(self):
        assert freshness_score("2 years ago") == 0.01

    def test_chinese_time(self):
        assert freshness_score("3 小时前") == 0.10
        assert freshness_score("2 天前") == 0.08

    def test_absolute_date_current_year(self):
        from datetime import datetime
        year = datetime.now().year
        assert freshness_score(f"{year}-06-01") == 0.05

    def test_absolute_date_old_year(self):
        assert freshness_score("2020-01-01") == 0.02

    def test_empty(self):
        assert freshness_score("") == 0.0

    def test_no_date_info(self):
        assert freshness_score("some random text") == 0.0


# ── 多引擎命中测试 ────────────────────────────────────────


class TestMultiEngineScore:
    def test_single_engine(self):
        assert multi_engine_score(1) == 0.0

    def test_two_engines(self):
        assert multi_engine_score(2) == 0.08

    def test_three_engines(self):
        assert multi_engine_score(3) == 0.15

    def test_many_engines(self):
        assert multi_engine_score(5) == 0.15

    def test_zero_engines(self):
        assert multi_engine_score(0) == 0.0


# ── 页面质量测试 ──────────────────────────────────────────


class TestPageQuality:
    def test_good_title(self):
        score = page_quality_score("A Comprehensive Guide to Python", "Long snippet " * 10, "https://example.com/guide")
        assert score > 0

    def test_short_title(self):
        score = page_quality_score("Hi", "", "https://example.com")
        assert score < 0.03  # 短标题扣分

    def test_long_snippet(self):
        score = page_quality_score("Good Title Here", "A" * 100, "https://example.com/page")
        assert score > 0

    def test_no_snippet(self):
        score = page_quality_score("Good Title Here", "", "https://example.com/page")
        assert score < 0.06  # 有标题分但无摘要分

    def test_short_url_path(self):
        score = page_quality_score("Title Here", "Snippet text " * 5, "https://example.com/guide")
        assert score > 0

    def test_long_url(self):
        url = "https://example.com/" + "a" * 200
        score = page_quality_score("Title Here", "Snippet text " * 5, url)
        assert score < 0.08  # 长 URL 扣分但仍可能为正

    def test_pdf_url(self):
        score = page_quality_score("Title Here", "Snippet text " * 5, "https://example.com/paper.pdf")
        assert score > 0.02

    def test_score_bounded(self):
        # 分数应在 0.0 ~ 0.1 之间
        score = page_quality_score("X", "", "x")
        assert 0.0 <= score <= 0.1


# ── 综合评分测试 ──────────────────────────────────────────


class TestComputeQualityBonus:
    def test_bonus_includes_all_signals(self):
        bonus = compute_quality_bonus(
            url="https://docs.python.org/3/tutorial",
            title="The Python Tutorial",
            snippet="Python is a programming language that lets you work quickly.",
            engine_count=2,
            published_age="3 days ago",
        )
        # 白名单域名 + 多引擎 + 新鲜度 + 质量
        assert bonus > 0.2

    def test_penalty_for_bad_domain(self):
        bonus = compute_quality_bonus(
            url="https://www.pinterest.com/pin/123",
            title="Pin",
            snippet="",
            engine_count=1,
        )
        assert bonus < 0  # 黑名单域名导致负分

    def test_single_engine_no_bonus(self):
        bonus = compute_quality_bonus(
            url="https://random-site.com/page",
            title="Random Page",
            snippet="Some content here for testing purposes with enough length.",
            engine_count=1,
        )
        # 单引擎、普通域名、无日期
        assert -0.05 < bonus < 0.15

    def test_bonus_range(self):
        # 极端情况也应有界
        bonus = compute_quality_bonus(
            url="https://docs.python.org/",
            title="Python Documentation",
            snippet="Official Python documentation with comprehensive guides and tutorials.",
            engine_count=5,
            published_age="1 hour ago",
        )
        assert bonus > 0
        assert bonus < 1.0  # 不应无限大
