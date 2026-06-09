"""
npm 搜索引擎。

使用 npm Registry Search API（免费，无需 API key）。
JavaScript/TypeScript 包搜索的最佳来源。
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

logger = logging.getLogger("scout.engines.npm")


class NpmEngine(Engine):
    """npm 搜索引擎。"""

    name = "npm"
    needs_browser = False
    supports_freshness = False
    supports_safesearch = False

    def build_url(
        self,
        query: str,
        max_results: int,
        filters: SearchFilters | None = None,
    ) -> str:
        """构建 npm 搜索 API URL。

        端点：https://registry.npmjs.org/-/v1/search
        """
        params = {
            "text": query,
            "size": str(min(max_results, 25)),
        }

        return f"https://registry.npmjs.org/-/v1/search?{urllib.parse.urlencode(params)}"

    def parse(self, data: str) -> list[SearchResult]:
        """解析 npm 搜索 API JSON 响应。"""
        results: list[SearchResult] = []

        try:
            payload = json.loads(data)
        except json.JSONDecodeError:
            logger.warning("npm JSON 解析失败")
            return results

        objects = payload.get("objects", [])

        for obj in objects:
            package = obj.get("package", {})

            name = package.get("name", "")
            version = package.get("version", "")
            description = package.get("description", "")
            keywords = package.get("keywords", [])
            publisher = package.get("publisher", {})
            links = package.get("links", {})
            date = package.get("date", "")

            if not name:
                continue

            # 构建 URL
            npm_url = links.get("npm", f"https://www.npmjs.com/package/{name}")

            # 构建摘要
            snippet_parts = []
            if description:
                snippet_parts.append(description)
            if version:
                snippet_parts.append(f"v{version}")
            if publisher.get("username"):
                snippet_parts.append(f"by {publisher['username']}")
            if keywords:
                snippet_parts.append(f"Tags: {', '.join(keywords[:5])}")
            if date:
                snippet_parts.append(f"Updated: {date[:10]}")

            snippet = " | ".join(snippet_parts) if snippet_parts else ""

            results.append(
                SearchResult(
                    title=f"{name} - {description}" if description else name,
                    url=npm_url,
                    snippet=snippet,
                    engine=self.name,
                    published_age=date[:10] if date else "",
                )
            )

        return results

    async def _fetch(self, url: str) -> str:
        """使用 aiohttp 抓取 npm JSON API。"""
        from ..config import settings
        from ..fetchers.http import _fetch_with_aiohttp

        return await _fetch_with_aiohttp(url, settings.request_timeout, None)


# 注册引擎
register_engine(NpmEngine())
