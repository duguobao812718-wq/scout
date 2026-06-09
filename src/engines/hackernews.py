"""
Hacker News 搜索引擎。

使用 Algolia HN Search API（免费，无需 API key，无反爬）。
技术新闻和讨论最佳来源。
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

logger = logging.getLogger("scout.engines.hackernews")


class HackerNewsEngine(Engine):
    """Hacker News 搜索引擎。"""

    name = "hackernews"
    needs_browser = False
    supports_freshness = True
    supports_safesearch = False

    def build_url(
        self,
        query: str,
        max_results: int,
        filters: SearchFilters | None = None,
    ) -> str:
        """构建 HN Search API URL。

        端点：https://hn.algolia.com/api/v1/search
        """
        filters = filters or SearchFilters()

        params = {
            "query": query,
            "hitsPerPage": str(min(max_results, 20)),
            "tags": "story",  # 只搜故事，不搜评论
        }

        # 新鲜度
        if filters.freshness:
            import time
            freshness_map = {
                "day": 86400,
                "week": 604800,
                "month": 2592000,
                "year": 31536000,
            }
            delta = freshness_map.get(filters.freshness, 31536000)
            params["numericFilters"] = f"created_at_i>{int(time.time()) - delta}"

        return f"https://hn.algolia.com/api/v1/search?{urllib.parse.urlencode(params)}"

    def parse(self, data: str) -> list[SearchResult]:
        """解析 HN Search API JSON 响应。"""
        results: list[SearchResult] = []

        try:
            payload = json.loads(data)
        except json.JSONDecodeError:
            logger.warning("HN JSON 解析失败")
            return results

        hits = payload.get("hits", [])

        for hit in hits:
            title = hit.get("title", "")
            url = hit.get("url", "")
            points = hit.get("points", 0)
            author = hit.get("author", "")
            num_comments = hit.get("num_comments", 0)
            created_at = hit.get("created_at", "")

            # 如果没有外部链接，使用 HN 讨论页
            if not url:
                object_id = hit.get("objectID", "")
                url = f"https://news.ycombinator.com/item?id={object_id}" if object_id else ""

            if not title or not url:
                continue

            # 构建摘要
            snippet_parts = []
            if points:
                snippet_parts.append(f"⬆ {points} points")
            if author:
                snippet_parts.append(f"by {author}")
            if num_comments:
                snippet_parts.append(f"💬 {num_comments} comments")
            if created_at:
                snippet_parts.append(f"📅 {created_at[:10]}")
            snippet = " | ".join(snippet_parts)

            results.append(
                SearchResult(
                    title=title,
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
register_engine(HackerNewsEngine())
