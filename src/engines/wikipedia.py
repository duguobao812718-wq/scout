"""
Wikipedia 搜索引擎。

使用 Wikipedia REST API（无需 API key，无反爬）。
最可靠的补充引擎，适合知识类查询。
"""

from __future__ import annotations

import json
import logging
import urllib.parse

from . import (
    Engine,
    SearchFilters,
    SearchResult,
    register_engine,
)

logger = logging.getLogger("scout.engines.wikipedia")

# 支持的语言版本
_LANG_MAP = {
    "en": "en", "zh": "zh", "de": "de", "fr": "fr", "es": "es",
    "ja": "ja", "ko": "ko", "ru": "ru", "pt": "pt", "it": "it",
}


class WikipediaEngine(Engine):
    """Wikipedia 搜索引擎。"""

    name = "wikipedia"
    needs_browser = False
    supports_freshness = False  # Wikipedia 内容不按时间过滤
    supports_safesearch = False

    def build_url(
        self,
        query: str,
        max_results: int,
        filters: SearchFilters | None = None,
    ) -> str:
        """构建 Wikipedia API URL。

        端点：https://{lang}.wikipedia.org/w/api.php
        """
        lang = self._get_lang()

        params = {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "srlimit": str(min(max_results, 50)),
            "srinfo": "totalhits|suggestion",
            "srprop": "snippet|timestamp|wordcount",
            "format": "json",
            "formatversion": "2",
        }

        return f"https://{lang}.wikipedia.org/w/api.php?{urllib.parse.urlencode(params)}"

    def _get_lang(self) -> str:
        """从配置获取语言。"""
        from ..config import settings
        region = settings.region or "en-us"
        lang = region.split("-")[0].lower()
        return _LANG_MAP.get(lang, "en")

    def parse(self, data: str) -> list[SearchResult]:
        """解析 Wikipedia JSON 响应。"""
        results: list[SearchResult] = []

        try:
            payload = json.loads(data)
        except json.JSONDecodeError:
            logger.warning("Wikipedia JSON 解析失败")
            return results

        lang = self._get_lang()
        search_results = payload.get("query", {}).get("search", [])

        for item in search_results:
            title = item.get("title", "")
            snippet = item.get("snippet", "")
            page_id = item.get("pageid", "")

            # 清理 HTML 标签（snippet 包含 <span class="searchmatch"> 标记）
            import re
            snippet = re.sub(r"<[^>]+>", "", snippet).strip()

            # 构建 URL
            url = f"https://{lang}.wikipedia.org/wiki/{urllib.parse.quote(title.replace(' ', '_'), safe='/')}"

            if title and url:
                results.append(
                    SearchResult(
                        title=f"{title} — Wikipedia",
                        url=url,
                        snippet=snippet,
                        engine=self.name,
                    )
                )

        return results

    async def _fetch(self, url: str) -> str:
        """使用 aiohttp 抓取 JSON API。"""
        from ..fetchers.http import _fetch_with_aiohttp
        from ..config import settings

        return await _fetch_with_aiohttp(url, settings.request_timeout, None)


# 注册引擎
register_engine(WikipediaEngine())
