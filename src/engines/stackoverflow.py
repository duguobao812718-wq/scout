"""
Stack Overflow 搜索引擎。

使用 Stack Exchange API（无需 API key，有速率限制 300 次/天）。
编程问答最佳来源。
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

logger = logging.getLogger("scout.engines.stackoverflow")


class StackOverflowEngine(Engine):
    """Stack Overflow 搜索引擎。"""

    name = "stackoverflow"
    needs_browser = False
    supports_freshness = True
    supports_safesearch = False

    def build_url(
        self,
        query: str,
        max_results: int,
        filters: SearchFilters | None = None,
    ) -> str:
        """构建 Stack Exchange API URL。

        端点：https://api.stackexchange.com/2.3/search/advanced
        """
        filters = filters or SearchFilters()

        params = {
            "q": query,
            "pagesize": str(min(max_results, 10)),
            "order": "desc",
            "sort": "relevance",
            "site": "stackoverflow",
            "filter": "default",
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
            params["fromdate"] = str(int(time.time()) - delta)

        return f"https://api.stackexchange.com/2.3/search/advanced?{urllib.parse.urlencode(params)}"

    def parse(self, data: str) -> list[SearchResult]:
        """解析 Stack Exchange API JSON 响应。"""
        results: list[SearchResult] = []

        try:
            payload = json.loads(data)
        except json.JSONDecodeError:
            logger.warning("StackOverflow JSON 解析失败")
            return results

        items = payload.get("items", [])

        for item in items:
            title = item.get("title", "")
            link = item.get("link", "")
            score = item.get("score", 0)
            answer_count = item.get("answer_count", 0)
            is_answered = item.get("is_answered", False)
            tags = item.get("tags", [])
            view_count = item.get("view_count", 0)
            creation_date = item.get("creation_date", 0)
            owner = item.get("owner", {})
            owner_name = owner.get("display_name", "")
            owner_reputation = owner.get("reputation", 0)

            if not title or not link:
                continue

            # 计算发布时间
            published_age = ""
            if creation_date:
                from datetime import datetime, timezone
                try:
                    created_dt = datetime.fromtimestamp(creation_date, tz=timezone.utc)
                    age = datetime.now(timezone.utc) - created_dt
                    if age.days > 365:
                        published_age = f"{age.days // 365} years ago"
                    elif age.days > 30:
                        published_age = f"{age.days // 30} months ago"
                    elif age.days > 0:
                        published_age = f"{age.days} days ago"
                    else:
                        hours = age.seconds // 3600
                        published_age = f"{hours} hours ago" if hours > 0 else "just now"
                except (ValueError, OSError):
                    pass

            # 构建摘要
            snippet_parts = []
            if is_answered:
                snippet_parts.append("✅ 已解决")
            snippet_parts.append(f"⬆ {score}")
            snippet_parts.append(f"💬 {answer_count} answers")
            snippet_parts.append(f"👁 {view_count:,} views")
            if owner_name:
                snippet_parts.append(f"👤 {owner_name}")
                if owner_reputation:
                    snippet_parts.append(f"({owner_reputation:,} rep)")
            if tags:
                snippet_parts.append(f"🏷️ {', '.join(tags[:3])}")
            if published_age:
                snippet_parts.append(f"📅 {published_age}")
            snippet = " | ".join(snippet_parts)

            results.append(
                SearchResult(
                    title=title,
                    url=link,
                    snippet=snippet,
                    engine=self.name,
                    published_age=published_age,
                )
            )

        return results

    async def _fetch(self, url: str) -> str:
        """使用 aiohttp 抓取 JSON API。"""
        from ..config import settings
        from ..fetchers.http import _fetch_with_aiohttp

        return await _fetch_with_aiohttp(url, settings.request_timeout, None)


# 注册引擎
register_engine(StackOverflowEngine())
