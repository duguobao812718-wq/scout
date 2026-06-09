"""
Yandex 搜索引擎。

Yandex 是俄罗斯最大的搜索引擎，对中文和俄文内容覆盖好。
使用 HTML 解析，反爬措施较弱。
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


class YandexEngine(Engine):
    """Yandex 搜索引擎。"""

    name = "yandex"
    needs_browser = False
    supports_freshness = True
    supports_safesearch = True

    def build_url(
        self,
        query: str,
        max_results: int,
        filters: SearchFilters | None = None,
    ) -> str:
        """构建 Yandex 搜索 URL。

        端点：https://yandex.com/search/
        """
        filters = filters or SearchFilters()

        params = {
            "text": query,
            "lr": "84",  # 默认美国，可通过 region 覆盖
        }

        # 区域
        from ..config import settings

        if settings.region:
            region_map = {
                "us": "84", "ru": "225", "cn": "134",
                "de": "94", "fr": "102", "gb": "106",
                "jp": "10632", "kr": "134",
            }
            country = settings.region.split("-")[0].lower()
            lr = region_map.get(country, "84")
            params["lr"] = lr

        # SafeSearch
        if settings.safesearch and settings.safesearch != "off":
            params["family"] = "yes"

        # 新鲜度
        if filters.freshness:
            freshness_map = {"day": "1", "week": "7", "month": "31", "year": "365"}
            fv = freshness_map.get(filters.freshness)
            if fv:
                params["within"] = "77"
                params["from_day"] = fv

        # 域名限制
        if filters.include_domains:
            for domain in filters.include_domains:
                params["text"] = f"{params['text']} site:{domain}"

        return f"https://yandex.com/search/?{urllib.parse.urlencode(params)}"

    def parse(self, html: str) -> list[SearchResult]:
        """解析 Yandex HTML 搜索结果。"""
        soup = parse_html(html)
        results: list[SearchResult] = []
        seen_urls: set[str] = set()

        # Yandex 使用 serp-item 或 OrganicTitle 容器
        items = soup.select("div.serp-item, li.serp-item")
        if not items:
            items = soup.select("div.OrganicTitleContentSpan, div.organic")

        for item in items:
            # 标题和链接
            link = item.select_one("a.OrganicTitle-Link, a.organic__url, a[href]")
            if not link:
                continue

            title_el = item.select_one("h3.OrganicTitle-Title, h3")
            title = text_of(title_el) if title_el else text_of(link)
            url = link.get("href", "")

            if not url or not url.startswith("http"):
                continue

            # 跳过 Yandex 内部链接
            if any(skip in url for skip in [
                "yandex.ru", "yandex.com", "ya.ru",
                "market.yandex", "mail.yandex",
            ]):
                continue

            # 归一化去重
            normalized = normalize_url(url)
            if normalized in seen_urls:
                continue
            seen_urls.add(normalized)

            # 摘要
            snippet = ""
            snippet_el = item.select_one("div.OrganicTextContentSpan, div.organic__content-wrapper, .snippet")
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
register_engine(YandexEngine())
