"""
Google Scholar 搜索引擎。

使用 SerpAPI 免费层不可行，直接 HTML 解析。
Google Scholar 反爬较强，使用 curl_cffi 浏览器指纹。
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


class GoogleScholarEngine(Engine):
    """Google Scholar 学术搜索引擎。"""

    name = "google_scholar"
    needs_browser = False
    supports_freshness = True
    supports_safesearch = False

    def build_url(
        self,
        query: str,
        max_results: int,
        filters: SearchFilters | None = None,
    ) -> str:
        """构建 Google Scholar 搜索 URL。

        端点：https://scholar.google.com/scholar
        """
        filters = filters or SearchFilters()

        params = {
            "q": query,
            "num": str(min(max_results, 20)),
            "hl": "en",
        }

        # 新鲜度（as_ylo 参数）
        if filters.freshness:
            from datetime import datetime
            year = datetime.now().year
            freshness_map = {"day": year, "week": year, "month": year, "year": year - 1}
            params["as_ylo"] = str(freshness_map.get(filters.freshness, year))

        return f"https://scholar.google.com/scholar?{urllib.parse.urlencode(params)}"

    def parse(self, html: str) -> list[SearchResult]:
        """解析 Google Scholar HTML 搜索结果。"""
        soup = parse_html(html)
        results: list[SearchResult] = []
        seen_urls: set[str] = set()

        # Google Scholar 使用 gs_r gs_or gs_scl 容器
        items = soup.select("div.gs_r.gs_or.gs_scl")
        if not items:
            items = soup.select("div.gs_ri")

        for item in items:
            # 标题和链接
            link = item.select_one("h3.gs_rt a")
            if not link:
                # 无链接的结果（可能是书籍）
                title_el = item.select_one("h3.gs_rt")
                if title_el:
                    title = text_of(title_el)
                    # 尝试从其他地方获取链接
                    link = item.select_one("div.gs_or_ggsm a")
                    if link:
                        url = link.get("href", "")
                    else:
                        continue
                else:
                    continue
            else:
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
            snippet_el = item.select_one("div.gs_rs")
            if snippet_el:
                snippet = text_of(snippet_el)

            # 作者和出版信息
            meta_el = item.select_one("div.gs_a")
            if meta_el:
                meta = text_of(meta_el)
                snippet = f"{meta} — {snippet}" if snippet else meta

            # 引用数
            cite_el = item.select_one("a[href*='cites']")
            citations = ""
            if cite_el:
                citations = text_of(cite_el)

            if title and url:
                full_snippet = snippet
                if citations:
                    full_snippet = f"引用: {citations} | {full_snippet}"
                results.append(
                    SearchResult(
                        title=title,
                        url=url,
                        snippet=full_snippet,
                        engine=self.name,
                    )
                )

        return results

    async def _fetch(self, url: str) -> str:
        """使用 curl_cffi 抓取（Google Scholar 需要浏览器指纹）。"""
        from ..fetchers.http import _fetch_with_curl_cffi
        from ..config import settings

        return await _fetch_with_curl_cffi(url, settings.request_timeout, None)


# 注册引擎
register_engine(GoogleScholarEngine())
