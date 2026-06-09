"""
DuckDuckGo 搜索引擎。

使用 DuckDuckGo 的 HTML 端点（非 JS），解析搜索结果。
参考：free-search-mcp 的 duckduckgo.py 实现。
"""

from __future__ import annotations

import urllib.parse

from . import (
    Engine,
    SearchFilters,
    SearchResult,
    extract_date_hint,
    freshness_value,
    parse_html,
    register_engine,
    safesearch_value,
    text_of,
)


class DuckDuckGoEngine(Engine):
    """DuckDuckGo 搜索引擎。"""

    name = "duckduckgo"
    needs_browser = False
    supports_freshness = True
    supports_safesearch = True

    def build_url(
        self,
        query: str,
        max_results: int,
        filters: SearchFilters | None = None,
    ) -> str:
        """构建 DuckDuckGo HTML 搜索 URL。

        端点：https://html.duckduckgo.com/html/
        """
        filters = filters or SearchFilters()

        params = {
            "q": query,
        }

        # SafeSearch
        ss = safesearch_value(self.name)
        if ss:
            params["kp"] = ss

        # 区域
        from ..config import settings

        if settings.region:
            params["kl"] = settings.region

        # 新鲜度
        if filters.freshness:
            fv = freshness_value(self.name, filters.freshness)
            if fv:
                params["df"] = fv

        # 域名限制
        if filters.include_domains:
            for domain in filters.include_domains:
                params["q"] = f"{params['q']} site:{domain}"

        return f"https://html.duckduckgo.com/html/?{urllib.parse.urlencode(params)}"

    def parse(self, html: str) -> list[SearchResult]:
        """解析 DuckDuckGo HTML 搜索结果。"""
        soup = parse_html(html)
        results: list[SearchResult] = []

        # 查找结果容器
        # DDG HTML 端点使用 div.result 或 div.web-result
        containers = soup.select("div.result, div.web-result")
        if not containers:
            # 备用选择器
            containers = soup.select(".results_links")

        for container in containers:
            # 跳过广告
            classes = container.get("class", [])
            if any(c in classes for c in ["result--ad", "result--sponsored"]):
                continue

            # 标题和链接
            link = container.select_one("a.result__a, a.result__url, .result__title a")
            if not link:
                continue

            title = text_of(link)
            url = link.get("href", "")

            # 解包 DDG 重定向 URL
            url = _unwrap_ddg_url(url)

            # 过滤 DDG 内部链接
            if not url or "duckduckgo.com/y.js" in url:
                continue
            if "ad_provider=" in url:
                continue

            # 摘要
            snippet_el = container.select_one(
                ".result__snippet, .result__body, .snippet"
            )
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


def _unwrap_ddg_url(url: str) -> str:
    """解包 DuckDuckGo 重定向 URL。

    DDG 将外部链接包装为 /l/?uddg=<encoded_url>&rut=...
    需要提取真实的目标 URL。
    """
    if not url:
        return ""

    # 处理相对 URL /l/?uddg=...
    if url.startswith("/l/"):
        parsed = urllib.parse.urlparse(f"https://duckduckgo.com{url}")
        qs = urllib.parse.parse_qs(parsed.query)
        if "uddg" in qs:
            return qs["uddg"][0]

    # 处理完整 URL https://duckduckgo.com/l/?uddg=...
    if "duckduckgo.com/l/" in url:
        parsed = urllib.parse.urlparse(url)
        qs = urllib.parse.parse_qs(parsed.query)
        if "uddg" in qs:
            return qs["uddg"][0]

    # 处理 //ddg.gg/ 短链接
    if url.startswith("//"):
        return f"https:{url}"

    return url


# 注册引擎
register_engine(DuckDuckGoEngine())
