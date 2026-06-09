"""
Bing 搜索引擎。

使用 Bing RSS feed 获取搜索结果（比 HTML 更可靠）。
参考：free-search-mcp 的 bing.py 实现。
"""

from __future__ import annotations

import re
import urllib.parse
import xml.etree.ElementTree as ET

from . import (
    Engine,
    SearchFilters,
    SearchResult,
    register_engine,
)


class BingEngine(Engine):
    """Bing 搜索引擎（使用 RSS feed）。"""

    name = "bing"
    needs_browser = False
    supports_freshness = True
    supports_safesearch = True

    def build_url(
        self,
        query: str,
        max_results: int,
        filters: SearchFilters | None = None,
    ) -> str:
        """构建 Bing RSS 搜索 URL。

        端点：https://www.bing.com/search?format=rss
        """
        filters = filters or SearchFilters()

        params = {
            "q": query,
            "format": "rss",
            "count": str(min(max_results, 50)),
        }

        # 区域 -> Bing 市场代码
        from ..config import settings

        market = _region_to_bing_market(settings.region)
        if market:
            params["mkt"] = market
            params["cc"] = market.split("-")[-1] if "-" in market else ""

        # SafeSearch
        if settings.safesearch:
            params["adlt"] = settings.safesearch

        # 新鲜度
        if filters.freshness:
            freshness_map = {"day": "ex1:ez1", "week": "ex1:ez2", "month": "ex1:ez3", "year": "ex1:ez4"}
            fv = freshness_map.get(filters.freshness)
            if fv:
                params["filters"] = fv

        # 域名限制
        if filters.include_domains:
            for domain in filters.include_domains:
                params["q"] = f"{params['q']} site:{domain}"

        return f"https://www.bing.com/search?{urllib.parse.urlencode(params)}"

    def parse(self, html: str) -> list[SearchResult]:
        """解析 Bing RSS 搜索结果。"""
        results: list[SearchResult] = []

        try:
            root = ET.fromstring(html)
        except ET.ParseError:
            return results

        # RSS 格式：<rss><channel><item>...</item></channel></rss>
        items = root.findall(".//item")

        for i, item in enumerate(items, 1):
            title_el = item.find("title")
            link_el = item.find("link")
            desc_el = item.find("description")

            title = title_el.text if title_el is not None and title_el.text else ""
            url = link_el.text if link_el is not None and link_el.text else ""
            snippet = desc_el.text if desc_el is not None and desc_el.text else ""

            # 清理 HTML 标签（Bing RSS 摘要可能包含 HTML）
            snippet = _strip_html(snippet)

            if title and url:
                results.append(
                    SearchResult(
                        title=title.strip(),
                        url=url.strip(),
                        snippet=snippet.strip(),
                        engine=self.name,
                        rank=i,
                    )
                )

        return results


def _strip_html(text: str) -> str:
    """简单的 HTML 标签清理。"""
    if not text:
        return ""
    # 移除 HTML 标签
    clean = re.sub(r"<[^>]+>", "", text)
    # 解码 HTML 实体
    clean = clean.replace("&amp;", "&")
    clean = clean.replace("&lt;", "<")
    clean = clean.replace("&gt;", ">")
    clean = clean.replace("&quot;", '"')
    clean = clean.replace("&#39;", "'")
    clean = clean.replace("&nbsp;", " ")
    return clean


def _region_to_bing_market(region: str) -> str:
    """将 Scout 区域代码转换为 Bing 市场代码。"""
    if not region:
        return "en-US"

    # 已经是 Bing 格式
    if "-" in region and len(region) == 5:
        parts = region.split("-")
        return f"{parts[0].lower()}-{parts[1].upper()}"

    # 简单映射
    mapping = {
        "us-en": "en-US",
        "gb-en": "en-GB",
        "zh-cn": "zh-CN",
        "zh-tw": "zh-TW",
        "ja-jp": "ja-JP",
        "ko-kr": "ko-KR",
        "de-de": "de-DE",
        "fr-fr": "fr-FR",
    }
    return mapping.get(region.lower(), "en-US")


# 注册引擎
register_engine(BingEngine())
