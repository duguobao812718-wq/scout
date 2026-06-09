"""
Reddit 搜索引擎。

使用 Reddit JSON API（免费，无需 API key）。
技术讨论、产品评测、深度分析的最佳来源。
"""

from __future__ import annotations

import json
import logging
import urllib.parse
from datetime import datetime, timezone

from ..config import settings
from . import (
    Engine,
    SearchFilters,
    SearchResult,
    register_engine,
)

logger = logging.getLogger("scout.engines.reddit")


class RedditEngine(Engine):
    """Reddit 搜索引擎。"""

    name = "reddit"
    needs_browser = False
    supports_freshness = True
    supports_safesearch = True

    # 排序方式
    _SORT_MAP = {
        "day": "new",
        "week": "top",
        "month": "top",
        "year": "top",
    }

    def build_url(
        self,
        query: str,
        max_results: int,
        filters: SearchFilters | None = None,
    ) -> str:
        """构建 Reddit 搜索 API URL。

        端点：https://www.reddit.com/search.json
        """
        filters = filters or SearchFilters()

        params = {
            "q": query,
            "limit": str(min(max_results, 25)),
            "type": "link",  # 只搜帖子，不搜评论
        }

        # 排序
        if filters.freshness:
            params["sort"] = self._SORT_MAP.get(filters.freshness, "relevance")
            params["t"] = filters.freshness  # time range for "top" sort
        else:
            params["sort"] = "relevance"

        # 安全搜索
        if settings.safesearch and settings.safesearch != "off":
            params["safe"] = "on"

        # 限定子版块
        if filters.include_domains:
            # Reddit 的 include_domains 可能是 subreddit 名称
            subreddits = [d.replace("r/", "") for d in filters.include_domains if d.startswith("r/")]
            if subreddits:
                # 搜索特定子版块
                subreddit = subreddits[0]
                return f"https://www.reddit.com/r/{subreddit}/search.json?{urllib.parse.urlencode(params)}"

        return f"https://www.reddit.com/search.json?{urllib.parse.urlencode(params)}"

    def parse(self, data: str) -> list[SearchResult]:
        """解析 Reddit JSON 响应。"""
        results: list[SearchResult] = []

        try:
            payload = json.loads(data)
        except json.JSONDecodeError:
            logger.warning("Reddit JSON 解析失败")
            return results

        posts = payload.get("data", {}).get("children", [])

        for post in posts:
            post_data = post.get("data", {})

            title = post_data.get("title", "")
            url = post_data.get("url", "")
            selftext = post_data.get("selftext", "")
            subreddit = post_data.get("subreddit", "")
            author = post_data.get("author", "")
            score = post_data.get("score", 0)
            num_comments = post_data.get("num_comments", 0)
            created_utc = post_data.get("created_utc", 0)
            is_self = post_data.get("is_self", False)
            permalink = post_data.get("permalink", "")

            if not title:
                continue

            # 如果是自帖，使用 Reddit 链接
            if is_self and permalink:
                url = f"https://www.reddit.com{permalink}"

            if not url:
                continue

            # 计算发布时间
            published_age = ""
            if created_utc:
                try:
                    created_dt = datetime.fromtimestamp(created_utc, tz=timezone.utc)
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
            if subreddit:
                snippet_parts.append(f"r/{subreddit}")
            if author:
                snippet_parts.append(f"u/{author}")
            if score:
                snippet_parts.append(f"⬆ {score}")
            if num_comments:
                snippet_parts.append(f"💬 {num_comments}")
            if published_age:
                snippet_parts.append(f"📅 {published_age}")

            snippet = " | ".join(snippet_parts)

            # 如果有正文摘要，添加到 snippet
            if selftext and not is_self:
                # 截取前 200 字符
                text_preview = selftext[:200].strip()
                if len(selftext) > 200:
                    text_preview += "..."
                if text_preview:
                    snippet = f"{snippet}\n{text_preview}"

            results.append(
                SearchResult(
                    title=title,
                    url=url,
                    snippet=snippet,
                    engine=self.name,
                    published_age=published_age,
                )
            )

        return results

    async def _fetch(self, url: str) -> str:
        """使用 aiohttp 抓取 Reddit JSON API。

        Reddit 要求 User-Agent 头。
        """
        from ..config import settings
        from ..fetchers.http import _fetch_with_aiohttp

        headers = {
            "User-Agent": "Scout/1.0 (AI Agent Search Tool)",
        }

        return await _fetch_with_aiohttp(url, settings.request_timeout, None, headers=headers)


# 注册引擎
register_engine(RedditEngine())
