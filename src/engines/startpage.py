"""
Startpage 搜索引擎。

Startpage 是 Google 的隐私前端，返回 Google 结果但不追踪用户。
使用 HTML 解析，需要 curl_cffi 浏览器指纹。
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


class StartpageEngine(Engine):
    """Startpage 搜索引擎。"""

    name = "startpage"
    needs_browser = False  # 通过 _fetch 覆盖使用 curl_cffi
    supports_freshness = True
    supports_safesearch = True

    def build_url(
        self,
        query: str,
        max_results: int,
        filters: SearchFilters | None = None,
    ) -> str:
        """构建 Startpage 搜索 URL。

        端点：https://www.startpage.com/sp/search
        """
        filters = filters or SearchFilters()

        params = {
            "query": query,
            "cat": "web",
        }

        # 新鲜度
        if filters.freshness:
            freshness_map = {"day": "1d", "week": "1w", "month": "1m", "year": "1y"}
            fv = freshness_map.get(filters.freshness)
            if fv:
                params["t"] = fv

        # 域名限制
        if filters.include_domains:
            for domain in filters.include_domains:
                params["query"] = f"{params['query']} site:{domain}"

        return f"https://www.startpage.com/sp/search?{urllib.parse.urlencode(params)}"

    def parse(self, html: str) -> list[SearchResult]:
        """解析 Startpage HTML 搜索结果。"""
        soup = parse_html(html)
        results: list[SearchResult] = []
        seen_urls: set[str] = set()

        # Startpage 使用 w-gl__result 容器
        items = soup.select("div.w-gl__result")
        if not items:
            items = soup.select("section.w-gl__result, div.result")

        for item in items:
            # 标题和链接
            link = item.select_one("a.w-gl__result-url, h3 a, a.result-link")
            if not link:
                link = item.select_one("a[href]")
                if not link:
                    continue

            title_el = item.select_one("h3.w-gl__result-title, h3")
            title = text_of(title_el) if title_el else text_of(link)
            url = link.get("href", "")

            if not url or not url.startswith("http"):
                continue

            # 归一化去重
            normalized = normalize_url(url)
            if normalized in seen_urls:
                continue
            seen_urls.add(normalized)

            # 摘要
            snippet = ""
            snippet_el = item.select_one("p.w-gl__description, p.result-description, .description")
            if snippet_el:
                snippet = text_of(snippet_el)

            # 日期提示
            date_text = extract_date_hint(snippet) or extract_date_hint(title)

            if title and url:
                results.append(
                    SearchResult(
                        title=title,
                        url=url,
                        snippet=snippet,
                        engine=self.name,
                        published_age=date_text,
                    )
                )

        return results

    async def _fetch(self, url: str) -> str:
        """使用 curl_cffi 抓取（Startpage 需要浏览器指纹）。"""
        from ..config import settings
        from ..fetchers.http import _fetch_with_curl_cffi

        return await _fetch_with_curl_cffi(url, settings.request_timeout, None)


# 注册引擎
register_engine(StartpageEngine())
