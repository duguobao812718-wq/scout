"""
DuckDuckGo News 搜索引擎。

DuckDuckGo 的新闻搜索，使用 HTML 解析。
需要 curl_cffi 浏览器指纹绕过 CAPTCHA。
"""

from __future__ import annotations

import urllib.parse

from ..utils import normalize_url
from . import (
    Engine,
    SearchFilters,
    SearchResult,
    extract_date_hint,
    parse_html,
    register_engine,
    text_of,
)


class DuckDuckGoNewsEngine(Engine):
    """DuckDuckGo News 搜索引擎。"""

    name = "ddg_news"
    needs_browser = False  # 通过 _fetch 覆盖使用 curl_cffi
    supports_freshness = True
    supports_safesearch = True

    def build_url(
        self,
        query: str,
        max_results: int,
        filters: SearchFilters | None = None,
    ) -> str:
        """构建 DuckDuckGo News 搜索 URL。

        端点：https://duckduckgo.com/?q=...&iar=news&ia=news
        """
        filters = filters or SearchFilters()

        params = {
            "q": query,
            "iar": "news",
            "ia": "news",
        }

        # 新鲜度
        if filters.freshness:
            freshness_map = {"day": "d", "week": "w", "month": "m", "year": "y"}
            fv = freshness_map.get(filters.freshness)
            if fv:
                params["df"] = fv

        # SafeSearch
        from ..config import settings
        if settings.safesearch:
            ss_map = {"strict": "1", "moderate": "-1", "off": "-2"}
            params["p"] = ss_map.get(settings.safesearch, "-1")

        # 域名限制
        if filters.include_domains:
            for domain in filters.include_domains:
                params["q"] = f"{params['q']} site:{domain}"

        return f"https://duckduckgo.com/?{urllib.parse.urlencode(params)}"

    def parse(self, html: str) -> list[SearchResult]:
        """解析 DuckDuckGo News HTML 搜索结果。"""
        soup = parse_html(html)
        results: list[SearchResult] = []
        seen_urls: set[str] = set()

        # DuckDuckGo 新闻结果使用 nrn-react-div 容器
        items = soup.select("article.result, div.result__body, div.nrn-react-div")
        if not items:
            items = soup.select("div.results--news div.result")

        for item in items:
            # 标题和链接
            link = item.select_one("a.result__a, a.result-link, a[href]")
            if not link:
                continue

            title = text_of(link)
            url = link.get("href", "")

            if not url or not url.startswith("http"):
                continue

            # 跳过 DuckDuckGo 内部链接
            if "duckduckgo.com" in url:
                continue

            # 归一化去重
            normalized = normalize_url(url)
            if normalized in seen_urls:
                continue
            seen_urls.add(normalized)

            # 摘要
            snippet = ""
            snippet_el = item.select_one("result__snippet, .result__snippet, .snippet")
            if snippet_el:
                snippet = text_of(snippet_el)

            # 来源
            source = ""
            source_el = item.select_one("span.result__source, .result__source")
            if source_el:
                source = text_of(source_el)

            # 日期提示
            date_text = extract_date_hint(snippet) or extract_date_hint(title)
            # DuckDuckGo 新闻通常有独立的日期元素
            date_el = item.select_one("time, span.result__date, .result__date")
            if date_el:
                date_text = text_of(date_el) or date_text

            if title and url:
                snippet_with_source = f"[{source}] {snippet}" if source else snippet
                results.append(
                    SearchResult(
                        title=title,
                        url=url,
                        snippet=snippet_with_source,
                        engine=self.name,
                        published_age=date_text,
                    )
                )

        return results

    async def _fetch(self, url: str) -> str:
        """使用 curl_cffi 抓取（DuckDuckGo 需要浏览器指纹）。"""
        from ..config import settings
        from ..fetchers.http import _fetch_with_curl_cffi

        return await _fetch_with_curl_cffi(url, settings.request_timeout, None)


# 注册引擎
register_engine(DuckDuckGoNewsEngine())
