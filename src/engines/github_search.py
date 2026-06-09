"""
GitHub 搜索引擎。

使用 GitHub 搜索 API（无需 API key，有速率限制 10 次/分钟）。
代码仓库和开发者最佳来源。
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

logger = logging.getLogger("scout.engines.github")


class GitHubEngine(Engine):
    """GitHub 搜索引擎。"""

    name = "github"
    needs_browser = False
    supports_freshness = True
    supports_safesearch = False

    def build_url(
        self,
        query: str,
        max_results: int,
        filters: SearchFilters | None = None,
    ) -> str:
        """构建 GitHub 搜索 API URL。

        端点：https://api.github.com/search/repositories
        """
        filters = filters or SearchFilters()

        search_query = query

        # 新鲜度
        if filters.freshness:
            from datetime import datetime, timedelta
            now = datetime.now()
            freshness_map = {
                "day": timedelta(days=1),
                "week": timedelta(weeks=1),
                "month": timedelta(days=30),
                "year": timedelta(days=365),
            }
            delta = freshness_map.get(filters.freshness, timedelta(days=365))
            from_date = (now - delta).strftime("%Y-%m-%d")
            search_query = f"{query} pushed:>{from_date}"

        params = {
            "q": search_query,
            "per_page": str(min(max_results, 10)),
            "sort": "best-match",
        }

        return f"https://api.github.com/search/repositories?{urllib.parse.urlencode(params)}"

    def parse(self, data: str) -> list[SearchResult]:
        """解析 GitHub 搜索 API JSON 响应。"""
        results: list[SearchResult] = []

        try:
            payload = json.loads(data)
        except json.JSONDecodeError:
            logger.warning("GitHub JSON 解析失败")
            return results

        items = payload.get("items", [])

        for item in items:
            name = item.get("full_name", "")
            description = item.get("description", "") or ""
            html_url = item.get("html_url", "")
            stars = item.get("stargazers_count", 0)
            language = item.get("language", "")
            topics = item.get("topics", [])
            updated_at = item.get("updated_at", "")

            if not name or not html_url:
                continue

            # 构建摘要
            snippet_parts = []
            if description:
                snippet_parts.append(description[:200])
            if stars:
                snippet_parts.append(f"⭐ {stars:,}")
            if language:
                snippet_parts.append(f"🔤 {language}")
            if topics:
                snippet_parts.append(f"🏷️ {', '.join(topics[:3])}")
            if updated_at:
                snippet_parts.append(f"📅 {updated_at[:10]}")
            snippet = " | ".join(snippet_parts)

            results.append(
                SearchResult(
                    title=name,
                    url=html_url,
                    snippet=snippet,
                    engine=self.name,
                )
            )

        return results

    async def _fetch(self, url: str) -> str:
        """使用 aiohttp 抓取 GitHub API。"""
        from ..fetchers.http import _fetch_with_aiohttp
        from ..config import settings

        return await _fetch_with_aiohttp(url, settings.request_timeout, None)


# 注册引擎
register_engine(GitHubEngine())
