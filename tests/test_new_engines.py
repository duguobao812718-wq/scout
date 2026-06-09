"""新引擎测试：Reddit, npm, PyPI, HuggingFace, Twitter。"""

from __future__ import annotations

import json

from src.engines import SearchFilters, get_engine, list_engines


class TestRedditEngine:
    """Reddit 引擎测试。"""

    def test_engine_registered(self):
        """Reddit 引擎已注册。"""
        engine = get_engine("reddit")
        assert engine.name == "reddit"

    def test_build_url_basic(self):
        """基本搜索 URL 构建。"""
        engine = get_engine("reddit")
        url = engine.build_url("python async", 10)
        assert "q=python+async" in url
        assert "limit=10" in url
        assert "reddit.com/search.json" in url

    def test_build_url_with_freshness(self):
        """带新鲜度的 URL 构建。"""
        engine = get_engine("reddit")
        filters = SearchFilters(freshness="week")
        url = engine.build_url("python", 10, filters)
        assert "sort=top" in url
        assert "t=week" in url

    def test_build_url_with_subreddit(self):
        """限定子版块的 URL 构建。"""
        engine = get_engine("reddit")
        filters = SearchFilters(include_domains=["r/python"])
        url = engine.build_url("async", 10, filters)
        assert "r/python/search.json" in url

    def test_parse_results(self):
        """解析搜索结果。"""
        engine = get_engine("reddit")
        data = json.dumps({
            "data": {
                "children": [
                    {
                        "data": {
                            "title": "Test Post",
                            "url": "https://example.com",
                            "subreddit": "python",
                            "author": "testuser",
                            "score": 100,
                            "num_comments": 50,
                            "created_utc": 1700000000,
                            "is_self": False,
                            "selftext": "This is a test post about Python.",
                        }
                    }
                ]
            }
        })
        results = engine.parse(data)
        assert len(results) == 1
        assert results[0].title == "Test Post"
        assert results[0].url == "https://example.com"
        assert "r/python" in results[0].snippet
        assert "⬆ 100" in results[0].snippet

    def test_parse_self_post(self):
        """解析自帖。"""
        engine = get_engine("reddit")
        data = json.dumps({
            "data": {
                "children": [
                    {
                        "data": {
                            "title": "Self Post",
                            "url": "",
                            "subreddit": "learnpython",
                            "author": "newbie",
                            "score": 10,
                            "num_comments": 5,
                            "created_utc": 1700000000,
                            "is_self": True,
                            "permalink": "/r/learnpython/comments/123/self_post",
                            "selftext": "How do I learn Python?",
                        }
                    }
                ]
            }
        })
        results = engine.parse(data)
        assert len(results) == 1
        assert "reddit.com" in results[0].url
        assert "/r/learnpython" in results[0].url

    def test_parse_empty(self):
        """解析空响应。"""
        engine = get_engine("reddit")
        results = engine.parse("{}")
        assert len(results) == 0

    def test_parse_invalid_json(self):
        """解析无效 JSON。"""
        engine = get_engine("reddit")
        results = engine.parse("invalid json")
        assert len(results) == 0


class TestNpmEngine:
    """npm 引擎测试。"""

    def test_engine_registered(self):
        """npm 引擎已注册。"""
        engine = get_engine("npm")
        assert engine.name == "npm"

    def test_build_url_basic(self):
        """基本搜索 URL 构建。"""
        engine = get_engine("npm")
        url = engine.build_url("react", 10)
        assert "text=react" in url
        assert "size=10" in url
        assert "registry.npmjs.org" in url

    def test_parse_results(self):
        """解析搜索结果。"""
        engine = get_engine("npm")
        data = json.dumps({
            "objects": [
                {
                    "package": {
                        "name": "react",
                        "version": "18.2.0",
                        "description": "A JavaScript library for building user interfaces",
                        "keywords": ["react", "javascript", "ui"],
                        "publisher": {"username": "react-bot"},
                        "links": {"npm": "https://www.npmjs.com/package/react"},
                        "date": "2023-01-01T00:00:00.000Z",
                    },
                    "score": {"final": 0.95},
                }
            ]
        })
        results = engine.parse(data)
        assert len(results) == 1
        assert "react" in results[0].title
        assert "react" in results[0].url
        assert "18.2.0" in results[0].snippet

    def test_parse_empty(self):
        """解析空响应。"""
        engine = get_engine("npm")
        results = engine.parse("{}")
        assert len(results) == 0


class TestPyPIEngine:
    """PyPI 引擎测试。"""

    def test_engine_registered(self):
        """PyPI 引擎已注册。"""
        engine = get_engine("pypi")
        assert engine.name == "pypi"

    def test_build_url_basic(self):
        """基本搜索 URL 构建。"""
        engine = get_engine("pypi")
        url = engine.build_url("requests", 10)
        assert "q=requests" in url
        assert "pypi.org/search" in url

    def test_parse_results(self):
        """解析搜索结果。"""
        engine = get_engine("pypi")
        html = '''
        <html>
        <body>
            <a class="package-snippet" href="/project/requests/">
                <span class="package-snippet__name">requests</span>
                <span class="package-snippet__version">2.31.0</span>
                <p class="package-snippet__description">Python HTTP for Humans.</p>
                <span class="package-snippet__created">Jan 1, 2023</span>
            </a>
        </body>
        </html>
        '''
        results = engine.parse(html)
        assert len(results) == 1
        assert "requests" in results[0].title
        assert "pypi.org/project/requests" in results[0].url

    def test_parse_empty(self):
        """解析空 HTML。"""
        engine = get_engine("pypi")
        results = engine.parse("<html><body></body></html>")
        assert len(results) == 0


class TestHuggingFaceEngine:
    """HuggingFace 引擎测试。"""

    def test_engine_registered(self):
        """HuggingFace 引擎已注册。"""
        engine = get_engine("huggingface")
        assert engine.name == "huggingface"

    def test_build_url_basic(self):
        """基本搜索 URL 构建。"""
        engine = get_engine("huggingface")
        url = engine.build_url("bert", 10)
        assert "search=bert" in url
        assert "limit=10" in url
        assert "huggingface.co/api/models" in url

    def test_build_url_dataset(self):
        """数据集搜索 URL 构建。"""
        engine = get_engine("huggingface")
        filters = SearchFilters(category="dataset")
        url = engine.build_url("squad", 10, filters)
        assert "huggingface.co/api/datasets" in url

    def test_parse_results(self):
        """解析搜索结果。"""
        engine = get_engine("huggingface")
        data = json.dumps([
            {
                "id": "bert-base-uncased",
                "author": "google",
                "pipeline_tag": "fill-mask",
                "tags": ["pytorch", "tf", "jax"],
                "downloads": 1000000,
                "likes": 500,
                "lastModified": "2023-01-01T00:00:00.000Z",
            }
        ])
        results = engine.parse(data)
        assert len(results) == 1
        assert "bert-base-uncased" in results[0].title
        assert "huggingface.co/bert-base-uncased" in results[0].url
        assert "fill-mask" in results[0].snippet

    def test_parse_empty(self):
        """解析空响应。"""
        engine = get_engine("huggingface")
        results = engine.parse("[]")
        assert len(results) == 0


class TestTwitterEngine:
    """Twitter 引擎测试。"""

    def test_engine_registered(self):
        """Twitter 引擎已注册。"""
        engine = get_engine("twitter")
        assert engine.name == "twitter"

    def test_build_url_basic(self):
        """基本搜索 URL 构建。"""
        engine = get_engine("twitter")
        url = engine.build_url("python", 10)
        assert "q=python" in url
        assert "nitter" in url
        assert "search" in url

    def test_build_url_with_freshness(self):
        """带新鲜度的 URL 构建。"""
        engine = get_engine("twitter")
        filters = SearchFilters(freshness="day")
        url = engine.build_url("python", 10, filters)
        assert "since=24h" in url

    def test_parse_results(self):
        """解析搜索结果。"""
        engine = get_engine("twitter")
        html = '''
        <html>
        <body>
            <div class="timeline-item">
                <a class="username" href="/testuser">@testuser</a>
                <a class="fullname" href="/testuser">Test User</a>
                <div class="tweet-content">This is a test tweet about Python programming.</div>
                <span class="tweet-date">Jan 1, 2023</span>
                <a class="tweet-link" href="/testuser/status/123456789"></a>
            </div>
        </body>
        </html>
        '''
        results = engine.parse(html)
        assert len(results) == 1
        assert "testuser" in results[0].title.lower() or "test tweet" in results[0].title.lower()
        assert "twitter.com" in results[0].url

    def test_parse_empty(self):
        """解析空 HTML。"""
        engine = get_engine("twitter")
        results = engine.parse("<html><body></body></html>")
        assert len(results) == 0


class TestMultimodalEngines:
    """多模态引擎测试。"""

    def test_youtube_engine_registered(self):
        """YouTube 引擎已注册。"""
        engine = get_engine("youtube")
        assert engine.name == "youtube"

    def test_youtube_build_url(self):
        """YouTube URL 构建。"""
        engine = get_engine("youtube")
        url = engine.build_url("python tutorial", 10)
        assert "search_query=python+tutorial" in url
        assert "youtube.com/results" in url

    def test_youtube_parse_empty(self):
        """YouTube 解析空 HTML。"""
        engine = get_engine("youtube")
        results = engine.parse("<html><body></body></html>")
        assert len(results) == 0

    def test_bilibili_engine_registered(self):
        """Bilibili 引擎已注册。"""
        engine = get_engine("bilibili")
        assert engine.name == "bilibili"

    def test_bilibili_build_url(self):
        """Bilibili URL 构建。"""
        engine = get_engine("bilibili")
        url = engine.build_url("Python 教程", 10)
        assert "keyword=" in url
        assert "api.bilibili.com" in url

    def test_bilibili_parse_results(self):
        """Bilibili 解析搜索结果。"""
        engine = get_engine("bilibili")
        data = json.dumps({
            "code": 0,
            "data": {
                "result": [
                    {
                        "title": "Python 入门教程",
                        "bvid": "BV1xx411c7mD",
                        "author": "UP主",
                        "play": 100000,
                        "duration": "10:30",
                        "pubdate": 1700000000,
                        "tag": "Python,编程,教程",
                    }
                ]
            }
        })
        results = engine.parse(data)
        assert len(results) == 1
        assert "Python" in results[0].title
        assert "bilibili.com" in results[0].url

    def test_bilibili_parse_empty(self):
        """Bilibili 解析空响应。"""
        engine = get_engine("bilibili")
        results = engine.parse("{}")
        assert len(results) == 0

    def test_unsplash_engine_registered(self):
        """Unsplash 引擎已注册。"""
        engine = get_engine("unsplash")
        assert engine.name == "unsplash"

    def test_unsplash_build_url(self):
        """Unsplash URL 构建。"""
        engine = get_engine("unsplash")
        url = engine.build_url("nature", 10)
        assert "unsplash.com/s/photos/nature" in url

    def test_unsplash_parse_empty(self):
        """Unsplash 解析空 HTML。"""
        engine = get_engine("unsplash")
        results = engine.parse("<html><body></body></html>")
        assert len(results) == 0

    def test_podcast_engine_registered(self):
        """Podcast 引擎已注册。"""
        engine = get_engine("podcast")
        assert engine.name == "podcast"

    def test_podcast_build_url(self):
        """Podcast URL 构建。"""
        engine = get_engine("podcast")
        url = engine.build_url("technology", 10)
        assert "term=technology" in url
        assert "itunes.apple.com" in url

    def test_podcast_parse_results(self):
        """Podcast 解析搜索结果。"""
        engine = get_engine("podcast")
        data = json.dumps({
            "results": [
                {
                    "trackName": "Tech Talk",
                    "artistName": "Tech Host",
                    "feedUrl": "https://example.com/feed.xml",
                    "trackViewUrl": "https://podcasts.apple.com/tech-talk",
                    "genres": ["Technology", "Science"],
                    "trackCount": 100,
                    "releaseDate": "2024-01-01T00:00:00Z",
                }
            ]
        })
        results = engine.parse(data)
        assert len(results) == 1
        assert "Tech Talk" in results[0].title
        assert "feed.xml" in results[0].url

    def test_podcast_parse_empty(self):
        """Podcast 解析空响应。"""
        engine = get_engine("podcast")
        results = engine.parse("{}")
        assert len(results) == 0


class TestEngineList:
    """引擎列表测试。"""

    def test_all_engines_registered(self):
        """所有引擎都已注册。"""
        engines = list_engines()
        expected = [
            "arxiv", "bilibili", "bing", "brave", "ddg_news", "duckduckgo",
            "github", "google", "google_scholar", "hackernews", "huggingface",
            "mojeek", "npm", "podcast", "pypi", "reddit", "searxng",
            "semantic_scholar", "stackoverflow", "startpage", "twitter",
            "unsplash", "wikipedia", "yandex", "youtube",
        ]
        for engine_name in expected:
            assert engine_name in engines, f"引擎 {engine_name} 未注册"

    def test_engine_count(self):
        """引擎数量正确。"""
        engines = list_engines()
        assert len(engines) == 26  # 22 + 新增 4 个多模态引擎
