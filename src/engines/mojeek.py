"""
Mojeek 搜索引擎。

Mojeek 是独立索引搜索引擎，不依赖 Google/Bing。
无反爬措施，使用标准 aiohttp 请求即可。
"""

from __future__ import annotations

import urllib.parse

from . import (
    Engine,
    SearchFilters,
    SearchResult,
    extract_date_hint,
    parse_html,
    register_engine,
    text_of,
)
from ..utils import normalize_url


class MojeekEngine(Engine):
    """Mojeek 搜索引擎。"""

    name = "mojeek"
    needs_browser = False
    supports_freshness = True
    supports_safesearch = True

    def build_url(
        self,
        query: str,
        max_results: int,
        filters: SearchFilters | None = None,
    ) -> str:
        """构建 Mojeek 搜索 URL。

        端点：https://www.mojeek.com/search
        """
        filters = filters or SearchFilters()

        params = {
            "q": query,
        }

        # 区域
        from ..config import settings

        if settings.region:
            # Mojeek 使用两位国家代码
            country = settings.region.split("-")[0] if "-" in settings.region else settings.region
            params["arc"] = country.lower()

        # SafeSearch
        if settings.safesearch and settings.safesearch != "off":
            params["safe"] = "1"

        # 新鲜度
        if filters.freshness:
            freshness_map = {"day": "1d", "week": "7d", "month": "31d", "year": "365d"}
            fv = freshness_map.get(filters.freshness)
            if fv:
                params["since"] = fv

        # 域名限制
        if filters.include_domains:
            for domain in filters.include_domains:
                params["q"] = f"{params['q']} site:{domain}"

        return f"https://www.mojeek.com/search?{urllib.parse.urlencode(params)}"

    def parse(self, html: str) -> list[SearchResult]:
        """解析 Mojeek HTML 搜索结果。"""
        soup = parse_html(html)
        results: list[SearchResult] = []
        seen_urls: set[str] = set()

        # Mojeek 使用 ul.results-standard > li 结构
        items = soup.select("ul.results-standard li")
        if not items:
            # 备用选择器
            items = soup.select("li.r1, li.r2, li.r3")

        for item in items:
            # 标题和链接
            link = item.select_one("h2 a.title, h2 a")
            if not link:
                link = item.select_one("a[href]")
                if not link:
                    continue

            title = text_of(link)
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
            snippet_el = item.select_one("p.s, p.snippet, .s")
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


# 注册引擎
register_engine(MojeekEngine())
