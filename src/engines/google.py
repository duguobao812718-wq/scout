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
from ..utils import normalize_url, unwrap_google_url


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

        # Google 搜索结果容器（按优先级尝试多种选择器）
        containers = soup.select("div.g")
        if not containers:
            containers = soup.select("div.tF2Cxc")
        if not containers:
            containers = soup.select("div.MjjYud")

        for container in containers:
            # 链接 - 优先从 yuRUbf（标准结果）获取
            link = container.select_one("div.yuRUbf a[href], a[href]")
            if not link:
                continue

            url = link.get("href", "")

            # 解包 Google 重定向 URL
            url = unwrap_google_url(url)

            # 过滤 Google 内部链接和无效链接
            if not url or not url.startswith("http"):
                continue
            if any(skip in url for skip in [
                "google.com", "google.co", "youtube.com/results",
                "accounts.google", "support.google", "policies.google",
            ]):
                continue

            # 去重（归一化后比较）
            normalized = normalize_url(url)
            if normalized in seen_urls:
                continue
            seen_urls.add(normalized)

            # 标题
            title_el = container.select_one("h3")
            title = text_of(title_el) if title_el else ""

            # 摘要 - 多个备用选择器
            snippet = ""
            snippet_selectors = [
                ".VwiC3b",   # 标准摘要
                ".IsZvec",   # 特征摘要
                ".s3v9rd",   # 备用摘要
                ".st",       # 旧版摘要
                ".lEBKkf",   # 新版摘要
                "span.aCOpRe",  # 行内摘要
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
register_engine(GoogleEngine())
