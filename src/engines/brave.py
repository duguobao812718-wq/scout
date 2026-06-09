"""
Brave 搜索引擎。

使用 Brave Search 的 HTML 页面解析搜索结果。
参考：free-search-mcp 的 brave.py 实现。
"""

from __future__ import annotations

import re
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


class BraveEngine(Engine):
    """Brave 搜索引擎。"""

    name = "brave"
    needs_browser = False
    supports_freshness = True
    supports_safesearch = True

    def build_url(
        self,
        query: str,
        max_results: int,
        filters: SearchFilters | None = None,
    ) -> str:
        """构建 Brave 搜索 URL。

        端点：https://search.brave.com/search
        """
        filters = filters or SearchFilters()

        params = {
            "q": query,
        }

        # SafeSearch
        from ..config import settings

        if settings.safesearch:
            params["safesearch"] = settings.safesearch

        # 区域
        if settings.region:
            # Brave 使用两位国家代码
            country = settings.region.split("-")[0] if "-" in settings.region else settings.region
            params["country"] = country

        # 新鲜度
        if filters.freshness:
            freshness_map = {"day": "pd", "week": "pw", "month": "pm", "year": "py"}
            fv = freshness_map.get(filters.freshness)
            if fv:
                params["tf"] = fv

        # 域名限制
        if filters.include_domains:
            for domain in filters.include_domains:
                params["q"] = f"{params['q']} site:{domain}"

        return f"https://search.brave.com/search?{urllib.parse.urlencode(params)}"

    def parse(self, html: str) -> list[SearchResult]:
        """解析 Brave HTML 搜索结果。"""
        soup = parse_html(html)
        results: list[SearchResult] = []
        seen_urls: set[str] = set()

        # Brave 使用 div.snippet[data-type="web"] 容器
        containers = soup.select('div.snippet[data-type="web"]')
        if not containers:
            containers = soup.select("div.snippet")
        if not containers:
            # 更宽泛的备用选择器
            containers = soup.select("div[id^='snippet-']")

        for container in containers:
            # 标题和链接 - 多种选择器
            link = container.select_one(
                "a.snippet-title, a.result-header, "
                "a[data-type='web'], "
                "div.snippet-title a"
            )
            if not link:
                # 尝试从容器内任意链接
                link = container.select_one("a[href]")
                if not link:
                    continue

            title = text_of(link)
            url = link.get("href", "")

            # 过滤 Brave 内部链接和无效链接
            if not url or not url.startswith("http"):
                continue
            if any(skip in url for skip in [
                "search.brave.com", "brave.com/search",
                "brave.com/app", "brave.com/news",
            ]):
                continue

            # 归一化去重
            normalized = normalize_url(url)
            if normalized in seen_urls:
                continue
            seen_urls.add(normalized)

            # 摘要
            snippet = ""
            snippet_selectors = [
                ".snippet-description",
                ".snippet-content",
                ".result-description",
                ".snippet-snippet",
                "p.snippet-description",
            ]
            for selector in snippet_selectors:
                el = container.select_one(selector)
                if el:
                    snippet = text_of(el)
                    if snippet:
                        break

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
register_engine(BraveEngine())
