"""
Google 搜索引擎。

使用 Google 搜索页面解析搜索结果。
参考：free-search-mcp 的 google.py 实现。
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


class GoogleEngine(Engine):
    """Google 搜索引擎。"""

    name = "google"
    needs_browser = False
    supports_freshness = True
    supports_safesearch = True

    def build_url(
        self,
        query: str,
        max_results: int,
        filters: SearchFilters | None = None,
    ) -> str:
        """构建 Google 搜索 URL。

        端点：https://www.google.com/search
        """
        filters = filters or SearchFilters()

        params = {
            "q": query,
            "num": str(min(max_results, 100)),
            "hl": "en",
        }

        # 区域
        from ..config import settings

        if settings.region:
            parts = settings.region.split("-")
            if len(parts) == 2:
                params["hl"] = parts[0]
                params["gl"] = parts[1].upper()

        # 新鲜度
        if filters.freshness:
            freshness_map = {"day": "qdr:d", "week": "qdr:w", "month": "qdr:m", "year": "qdr:y"}
            fv = freshness_map.get(filters.freshness)
            if fv:
                params["tbs"] = fv

        # 域名限制
        if filters.include_domains:
            for domain in filters.include_domains:
                params["q"] = f"{params['q']} site:{domain}"

        return f"https://www.google.com/search?{urllib.parse.urlencode(params)}"

    def parse(self, html: str) -> list[SearchResult]:
        """解析 Google HTML 搜索结果。"""
        soup = parse_html(html)
        results: list[SearchResult] = []
        seen_urls: set[str] = set()

        # Google 使用 div.g 或 div[data-hveid] 容器
        containers = soup.select("div.g, div[data-hveid]")
        if not containers:
            # 备用选择器
            containers = soup.select(".tF2Cxc, .MjjYud")

        for container in containers:
            # 标题和链接
            link = container.select_one("a[href]")
            if not link:
                continue

            url = link.get("href", "")

            # 解包 Google 重定向 URL
            url = _unwrap_google_url(url)

            # 过滤 Google 内部链接
            if not url or "google.com" in url:
                continue

            # 去重
            if url in seen_urls:
                continue
            seen_urls.add(url)

            # 标题
            title_el = container.select_one("h3, .LC20lb, .DKV0Md")
            title = text_of(title_el) if title_el else ""

            # 摘要 - 多个备用选择器
            snippet = ""
            snippet_selectors = [
                ".VwiC3b",
                ".IsZvec",
                ".s3v9rd",
                ".st",
                ".lEBKkf",
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


def _unwrap_google_url(url: str) -> str:
    """解包 Google 重定向 URL。

    Google 将外部链接包装为 /url?q=<target>&...
    """
    if not url:
        return ""

    # 处理相对 URL
    if url.startswith("/url?"):
        parsed = urllib.parse.urlparse(f"https://www.google.com{url}")
        qs = urllib.parse.parse_qs(parsed.query)
        if "q" in qs:
            return qs["q"][0]

    # 处理直接链接
    if url.startswith("http"):
        return url

    return url


# 注册引擎
register_engine(GoogleEngine())
