"""搜索引擎 HTML 解析测试。"""

import json

import pytest

from src.engines.bing import BingEngine
from src.engines.brave import BraveEngine
from src.engines.google import GoogleEngine
from src.engines.duckduckgo import DuckDuckGoEngine
from src.engines.mojeek import MojeekEngine
from src.engines.searxng import SearxNGEngine
from src.engines.academic import SemanticScholarEngine, ArxivEngine
from src.engines.wikipedia import WikipediaEngine
from src.engines.startpage import StartpageEngine
from src.engines.yandex import YandexEngine
from src.engines.ddg_news import DuckDuckGoNewsEngine


# ── Google 解析测试 ───────────────────────────────────────


class TestGoogleParse:
    """Google HTML 解析测试。"""

    # 模拟 Google 搜索结果 HTML
    GOOGLE_HTML = """
    <html><body>
    <div class="g">
        <div class="yuRUbf">
            <a href="https://www.python.org/">
                <h3>Welcome to Python.org</h3>
            </a>
        </div>
        <div class="VwiC3b">The official home of the Python Programming Language.</div>
    </div>
    <div class="g">
        <div class="yuRUbf">
            <a href="/url?q=https://docs.python.org/3/tutorial/&source=example">
                <h3>Python Tutorial — Python 3 docs</h3>
            </a>
        </div>
        <div class="VwiC3b">An informal introduction to Python.</div>
    </div>
    <div class="g">
        <div class="yuRUbf">
            <a href="https://www.google.com/search?q=test">
                <h3>Google Internal Link</h3>
            </a>
        </div>
    </div>
    </body></html>
    """

    def test_parse_results(self):
        engine = GoogleEngine()
        results = engine.parse(self.GOOGLE_HTML)
        assert len(results) == 2  # Google 内部链接被过滤

    def test_parse_titles(self):
        engine = GoogleEngine()
        results = engine.parse(self.GOOGLE_HTML)
        assert results[0].title == "Welcome to Python.org"
        assert results[1].title == "Python Tutorial — Python 3 docs"

    def test_parse_urls(self):
        engine = GoogleEngine()
        results = engine.parse(self.GOOGLE_HTML)
        assert results[0].url == "https://www.python.org/"
        # 第二个 URL 应被解包
        assert results[1].url == "https://docs.python.org/3/tutorial/"

    def test_parse_snippets(self):
        engine = GoogleEngine()
        results = engine.parse(self.GOOGLE_HTML)
        assert "Python Programming Language" in results[0].snippet
        assert "informal introduction" in results[1].snippet

    def test_filters_google_internal(self):
        engine = GoogleEngine()
        results = engine.parse(self.GOOGLE_HTML)
        urls = [r.url for r in results]
        assert all("google.com" not in u for u in urls)

    def test_empty_html(self):
        engine = GoogleEngine()
        results = engine.parse("<html><body></body></html>")
        assert results == []

    def test_dedup_by_normalized_url(self):
        """相同页面不同变体应去重。"""
        html = """
        <html><body>
        <div class="g">
            <div class="yuRUbf"><a href="https://www.example.com/page?utm_source=google"><h3>Page</h3></a></div>
            <div class="VwiC3b">Snippet 1</div>
        </div>
        <div class="g">
            <div class="yuRUbf"><a href="https://example.com/page/"><h3>Page</h3></a></div>
            <div class="VwiC3b">Snippet 2</div>
        </div>
        </body></html>
        """
        engine = GoogleEngine()
        results = engine.parse(html)
        assert len(results) == 1


# ── Brave 解析测试 ────────────────────────────────────────


class TestBraveParse:
    """Brave HTML 解析测试。"""

    BRAVE_HTML = """
    <html><body>
    <div class="snippet" data-type="web">
        <a class="snippet-title" href="https://www.rust-lang.org/">Rust Programming Language</a>
        <p class="snippet-description">A language empowering everyone to build reliable software.</p>
    </div>
    <div class="snippet" data-type="web">
        <a class="snippet-title" href="https://doc.rust-lang.org/book/">The Rust Programming Language</a>
        <p class="snippet-description">The Rust book, officially.</p>
    </div>
    <div class="snippet" data-type="web">
        <a class="snippet-title" href="https://search.brave.com/internal">Internal Link</a>
        <p class="snippet-description">Should be filtered.</p>
    </div>
    </body></html>
    """

    def test_parse_results(self):
        engine = BraveEngine()
        results = engine.parse(self.BRAVE_HTML)
        assert len(results) == 2  # Brave 内部链接被过滤

    def test_parse_titles(self):
        engine = BraveEngine()
        results = engine.parse(self.BRAVE_HTML)
        assert results[0].title == "Rust Programming Language"
        assert results[1].title == "The Rust Programming Language"

    def test_filters_brave_internal(self):
        engine = BraveEngine()
        results = engine.parse(self.BRAVE_HTML)
        urls = [r.url for r in results]
        assert all("brave.com" not in u for u in urls)

    def test_empty_html(self):
        engine = BraveEngine()
        results = engine.parse("<html><body></body></html>")
        assert results == []


# ── DuckDuckGo 解析测试 ───────────────────────────────────


class TestDuckDuckGoParse:
    """DuckDuckGo HTML 解析测试。"""

    DDG_HTML = """
    <html><body>
    <div class="result results_links results_links_deep web-result">
        <a class="result__a" href="https://example.com/page1">Example Page 1</a>
        <a class="result__snippet">This is the first example page.</a>
    </div>
    <div class="result results_links results_links_deep web-result">
        <a class="result__a" href="https://example.com/page2">Example Page 2</a>
        <a class="result__snippet">This is the second example page.</a>
    </div>
    </body></html>
    """

    def test_parse_results(self):
        engine = DuckDuckGoEngine()
        results = engine.parse(self.DDG_HTML)
        assert len(results) >= 1  # 至少解析出一个结果

    def test_empty_html(self):
        engine = DuckDuckGoEngine()
        results = engine.parse("<html><body></body></html>")
        assert results == []


# ── 引擎 URL 构建测试（补充） ─────────────────────────────


class TestBuildUrl:
    """URL 构建测试补充。"""

    def test_google_url_has_query(self):
        engine = GoogleEngine()
        url = engine.build_url("test query", 10)
        assert "q=test+query" in url or "q=test%20query" in url

    def test_brave_url_has_query(self):
        engine = BraveEngine()
        url = engine.build_url("test query", 10)
        assert "q=test+query" in url or "q=test%20query" in url

    def test_google_url_with_domain_filter(self):
        engine = GoogleEngine()
        from src.engines import SearchFilters
        filters = SearchFilters(include_domains=["github.com"])
        url = engine.build_url("python", 10, filters=filters)
        # URL 编码后 : 变为 %3A
        assert "site:github.com" in url or "site%3Agithub.com" in url

    def test_brave_url_with_freshness(self):
        engine = BraveEngine()
        from src.engines import SearchFilters
        filters = SearchFilters(freshness="week")
        url = engine.build_url("test", 10, filters=filters)
        assert "tf=pw" in url

    def test_mojeek_url_has_query(self):
        engine = MojeekEngine()
        url = engine.build_url("test query", 10)
        assert "q=test+query" in url or "q=test%20query" in url

    def test_searxng_url_has_query(self):
        engine = SearxNGEngine()
        url = engine.build_url("test query", 10)
        assert "q=test+query" in url or "q=test%20query" in url

    def test_searxng_url_with_freshness(self):
        engine = SearxNGEngine()
        from src.engines import SearchFilters
        filters = SearchFilters(freshness="day")
        url = engine.build_url("test", 10, filters=filters)
        assert "time_range=day" in url


# ── Mojeek 解析测试 ──────────────────────────────────────


class TestMojeekParse:
    """Mojeek HTML 解析测试。"""

    MOJEEK_HTML = """
    <html><body>
    <ul class="results-standard">
        <li class="r1">
            <h2><a class="title" href="https://example.com/page1">Example Page 1</a></h2>
            <p class="s">This is the first example snippet.</p>
        </li>
        <li class="r2">
            <h2><a class="title" href="https://example.com/page2">Example Page 2</a></h2>
            <p class="s">This is the second example snippet.</p>
        </li>
    </ul>
    </body></html>
    """

    def test_parse_results(self):
        engine = MojeekEngine()
        results = engine.parse(self.MOJEEK_HTML)
        assert len(results) == 2

    def test_parse_titles(self):
        engine = MojeekEngine()
        results = engine.parse(self.MOJEEK_HTML)
        assert results[0].title == "Example Page 1"
        assert results[1].title == "Example Page 2"

    def test_parse_snippets(self):
        engine = MojeekEngine()
        results = engine.parse(self.MOJEEK_HTML)
        assert "first example" in results[0].snippet
        assert "second example" in results[1].snippet

    def test_empty_html(self):
        engine = MojeekEngine()
        results = engine.parse("<html><body></body></html>")
        assert results == []


# ── SearXNG 解析测试 ─────────────────────────────────────


class TestSearxNGParse:
    """SearXNG HTML 解析测试。"""

    SEARX_HTML = """
    <html><body>
    <div id="results">
        <article class="result">
            <h3><a href="https://python.org/">Welcome to Python.org</a></h3>
            <p class="content">The official Python website.</p>
        </article>
        <article class="result">
            <h3><a href="https://docs.python.org/3/">Python 3 Documentation</a></h3>
            <p class="content">Official Python 3 docs.</p>
        </article>
        <article class="result result-ad">
            <h3><a href="https://ad.example.com/">Ad Result</a></h3>
            <p class="content">This is an ad.</p>
        </article>
    </div>
    </body></html>
    """

    def test_parse_results(self):
        engine = SearxNGEngine()
        results = engine.parse(self.SEARX_HTML)
        assert len(results) == 2  # 广告被过滤

    def test_parse_titles(self):
        engine = SearxNGEngine()
        results = engine.parse(self.SEARX_HTML)
        assert results[0].title == "Welcome to Python.org"
        assert results[1].title == "Python 3 Documentation"

    def test_filters_ads(self):
        engine = SearxNGEngine()
        results = engine.parse(self.SEARX_HTML)
        titles = [r.title for r in results]
        assert "Ad Result" not in titles

    def test_empty_html(self):
        engine = SearxNGEngine()
        results = engine.parse("<html><body></body></html>")
        assert results == []


# ── Semantic Scholar 解析测试 ─────────────────────────────


class TestSemanticScholarParse:
    """Semantic Scholar JSON 解析测试。"""

    SS_JSON = json.dumps({
        "total": 2,
        "data": [
            {
                "paperId": "abc123",
                "title": "Deep Learning for NLP",
                "abstract": "This paper surveys deep learning methods for NLP.",
                "year": 2023,
                "venue": "ACL",
                "citationCount": 150,
                "authors": [{"name": "John Doe"}, {"name": "Jane Smith"}],
                "publicationDate": "2023-01-15",
            },
            {
                "paperId": "def456",
                "title": "Transformers Explained",
                "abstract": "An introduction to transformer architectures.",
                "year": 2024,
                "venue": "NeurIPS",
                "citationCount": 50,
                "authors": [{"name": "Alice Johnson"}],
            },
        ],
    })

    def test_parse_results(self):
        engine = SemanticScholarEngine()
        results = engine.parse(self.SS_JSON)
        assert len(results) == 2

    def test_parse_titles(self):
        engine = SemanticScholarEngine()
        results = engine.parse(self.SS_JSON)
        assert results[0].title == "Deep Learning for NLP"
        assert results[1].title == "Transformers Explained"

    def test_parse_urls(self):
        engine = SemanticScholarEngine()
        results = engine.parse(self.SS_JSON)
        assert "semanticscholar.org/paper/abc123" in results[0].url

    def test_parse_snippets_contain_metadata(self):
        engine = SemanticScholarEngine()
        results = engine.parse(self.SS_JSON)
        # 摘要应包含年份、引用数、作者
        assert "2023" in results[0].snippet
        assert "150" in results[0].snippet
        assert "John Doe" in results[0].snippet

    def test_empty_json(self):
        engine = SemanticScholarEngine()
        results = engine.parse('{"data": []}')
        assert results == []

    def test_invalid_json(self):
        engine = SemanticScholarEngine()
        results = engine.parse("not json")
        assert results == []


# ── arXiv 解析测试 ────────────────────────────────────────


class TestArxivParse:
    """arXiv Atom XML 解析测试。"""

    ARXIV_XML = """<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
        <entry>
            <id>http://arxiv.org/abs/2301.00001v1</id>
            <title>Attention Is All You Need</title>
            <summary>We propose a new simple network architecture called the Transformer.</summary>
            <published>2023-01-01T00:00:00Z</published>
            <author><name>Ashish Vaswani</name></author>
            <author><name>Noam Shazeer</name></author>
            <link type="text/html" href="https://arxiv.org/abs/2301.00001v1"/>
        </entry>
        <entry>
            <id>http://arxiv.org/abs/2301.00002v1</id>
            <title>BERT: Pre-training of Deep Bidirectional Transformers</title>
            <summary>We introduce BERT, a new language representation model.</summary>
            <published>2023-01-02T00:00:00Z</published>
            <author><name>Jacob Devlin</name></author>
            <link type="text/html" href="https://arxiv.org/abs/2301.00002v1"/>
        </entry>
    </feed>"""

    def test_parse_results(self):
        engine = ArxivEngine()
        results = engine.parse(self.ARXIV_XML)
        assert len(results) == 2

    def test_parse_titles(self):
        engine = ArxivEngine()
        results = engine.parse(self.ARXIV_XML)
        assert "Attention" in results[0].title
        assert "BERT" in results[1].title

    def test_parse_snippets_contain_authors(self):
        engine = ArxivEngine()
        results = engine.parse(self.ARXIV_XML)
        assert "Ashish Vaswani" in results[0].snippet
        assert "Jacob Devlin" in results[1].snippet

    def test_parse_snippets_contain_date(self):
        engine = ArxivEngine()
        results = engine.parse(self.ARXIV_XML)
        assert "2023-01-01" in results[0].snippet

    def test_empty_xml(self):
        engine = ArxivEngine()
        results = engine.parse('<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"></feed>')
        assert results == []


# ── Wikipedia 解析测试 ─────────────────────────────────────


class TestWikipediaParse:
    """Wikipedia JSON 解析测试。"""

    WIKI_JSON = json.dumps({
        "query": {
            "search": [
                {
                    "title": "Python (programming language)",
                    "pageid": 12345,
                    "snippet": "Python is a <span class=\"searchmatch\">high-level</span> programming language.",
                    "timestamp": "2023-06-01T00:00:00Z",
                    "wordcount": 5000,
                },
                {
                    "title": "Monty Python",
                    "pageid": 67890,
                    "snippet": "Monty Python is a <span class=\"searchmatch\">comedy</span> group.",
                    "timestamp": "2023-05-01T00:00:00Z",
                    "wordcount": 3000,
                },
            ],
        },
    })

    def test_parse_results(self):
        engine = WikipediaEngine()
        results = engine.parse(self.WIKI_JSON)
        assert len(results) == 2

    def test_parse_titles_contain_wikipedia(self):
        engine = WikipediaEngine()
        results = engine.parse(self.WIKI_JSON)
        assert "Wikipedia" in results[0].title

    def test_parse_urls(self):
        engine = WikipediaEngine()
        results = engine.parse(self.WIKI_JSON)
        assert "wikipedia.org/wiki/" in results[0].url

    def test_parse_snippets_no_html(self):
        engine = WikipediaEngine()
        results = engine.parse(self.WIKI_JSON)
        # HTML 标签应被清理
        assert "<span" not in results[0].snippet
        assert "high-level" in results[0].snippet

    def test_empty_json(self):
        engine = WikipediaEngine()
        results = engine.parse('{"query": {"search": []}}')
        assert results == []

    def test_invalid_json(self):
        engine = WikipediaEngine()
        results = engine.parse("not json")
        assert results == []

    def test_build_url(self):
        engine = WikipediaEngine()
        url = engine.build_url("Python", 10)
        assert "wikipedia.org/w/api.php" in url
        assert "srsearch=Python" in url


# ── Startpage 解析测试 ─────────────────────────────────────


class TestStartpageParse:
    """Startpage HTML 解析测试。"""

    STARTPAGE_HTML = """
    <html><body>
    <div class="w-gl__result">
        <h3 class="w-gl__result-title">
            <a class="w-gl__result-url" href="https://www.python.org/">Python.org</a>
        </h3>
        <p class="w-gl__description">The official Python website.</p>
    </div>
    <div class="w-gl__result">
        <h3 class="w-gl__result-title">
            <a class="w-gl__result-url" href="https://docs.python.org/">Python Docs</a>
        </h3>
        <p class="w-gl__description">Python documentation.</p>
    </div>
    </body></html>
    """

    def test_parse_results(self):
        engine = StartpageEngine()
        results = engine.parse(self.STARTPAGE_HTML)
        assert len(results) == 2

    def test_parse_titles(self):
        engine = StartpageEngine()
        results = engine.parse(self.STARTPAGE_HTML)
        assert results[0].title == "Python.org"
        assert results[1].title == "Python Docs"

    def test_parse_urls(self):
        engine = StartpageEngine()
        results = engine.parse(self.STARTPAGE_HTML)
        assert results[0].url == "https://www.python.org/"

    def test_parse_snippets(self):
        engine = StartpageEngine()
        results = engine.parse(self.STARTPAGE_HTML)
        assert "official" in results[0].snippet

    def test_empty_html(self):
        engine = StartpageEngine()
        results = engine.parse("<html><body></body></html>")
        assert results == []

    def test_build_url(self):
        engine = StartpageEngine()
        url = engine.build_url("Python", 10)
        assert "startpage.com/sp/search" in url
        assert "query=Python" in url


# ── Yandex 解析测试 ────────────────────────────────────────


class TestYandexParse:
    """Yandex HTML 解析测试。"""

    YANDEX_HTML = """
    <html><body>
    <div class="serp-item">
        <h3><a href="https://www.python.org/">Python.org</a></h3>
        <div class="OrganicTextContentSpan">The official Python website.</div>
    </div>
    <div class="serp-item">
        <h3><a href="https://docs.python.org/">Python Docs</a></h3>
        <div class="OrganicTextContentSpan">Python documentation.</div>
    </div>
    </body></html>
    """

    def test_parse_results(self):
        engine = YandexEngine()
        results = engine.parse(self.YANDEX_HTML)
        assert len(results) == 2

    def test_parse_titles(self):
        engine = YandexEngine()
        results = engine.parse(self.YANDEX_HTML)
        assert results[0].title == "Python.org"

    def test_parse_urls(self):
        engine = YandexEngine()
        results = engine.parse(self.YANDEX_HTML)
        assert results[0].url == "https://www.python.org/"

    def test_skip_yandex_internal(self):
        engine = YandexEngine()
        html = """
        <html><body>
        <div class="serp-item">
            <h3><a href="https://yandex.ru/search">Yandex Search</a></h3>
            <div class="OrganicTextContentSpan">Internal link</div>
        </div>
        <div class="serp-item">
            <h3><a href="https://www.python.org/">Python</a></h3>
            <div class="OrganicTextContentSpan">External link</div>
        </div>
        </body></html>
        """
        results = engine.parse(html)
        assert len(results) == 1
        assert "python.org" in results[0].url

    def test_empty_html(self):
        engine = YandexEngine()
        results = engine.parse("<html><body></body></html>")
        assert results == []

    def test_build_url(self):
        engine = YandexEngine()
        url = engine.build_url("Python", 10)
        assert "yandex.com/search" in url
        assert "text=Python" in url


# ── DuckDuckGo News 解析测试 ───────────────────────────────


class TestDuckDuckGoNewsParse:
    """DuckDuckGo News HTML 解析测试。"""

    DDG_NEWS_HTML = """
    <html><body>
    <article class="result">
        <a class="result__a" href="https://news.example.com/article1">Breaking News Title</a>
        <span class="result__source">Example News</span>
        <p class="result__snippet">This is a news snippet.</p>
        <time>2 hours ago</time>
    </article>
    <article class="result">
        <a class="result__a" href="https://news.example.com/article2">Another News</a>
        <span class="result__source">Other Source</span>
        <p class="result__snippet">Another news snippet.</p>
    </article>
    </body></html>
    """

    def test_parse_results(self):
        engine = DuckDuckGoNewsEngine()
        results = engine.parse(self.DDG_NEWS_HTML)
        assert len(results) == 2

    def test_parse_titles(self):
        engine = DuckDuckGoNewsEngine()
        results = engine.parse(self.DDG_NEWS_HTML)
        assert results[0].title == "Breaking News Title"

    def test_parse_source_in_snippet(self):
        engine = DuckDuckGoNewsEngine()
        results = engine.parse(self.DDG_NEWS_HTML)
        assert "Example News" in results[0].snippet

    def test_parse_date(self):
        engine = DuckDuckGoNewsEngine()
        results = engine.parse(self.DDG_NEWS_HTML)
        assert "2 hours ago" in results[0].published_age

    def test_skip_ddg_internal(self):
        engine = DuckDuckGoNewsEngine()
        html = """
        <html><body>
        <article class="result">
            <a class="result__a" href="https://duckduckgo.com/about">DDG About</a>
            <p class="result__snippet">Internal</p>
        </article>
        <article class="result">
            <a class="result__a" href="https://news.example.com/real">Real News</a>
            <p class="result__snippet">External</p>
        </article>
        </body></html>
        """
        results = engine.parse(html)
        assert len(results) == 1
        assert "example.com" in results[0].url

    def test_empty_html(self):
        engine = DuckDuckGoNewsEngine()
        results = engine.parse("<html><body></body></html>")
        assert results == []

    def test_build_url(self):
        engine = DuckDuckGoNewsEngine()
        url = engine.build_url("Python", 10)
        assert "duckduckgo.com" in url
        assert "iar=news" in url
