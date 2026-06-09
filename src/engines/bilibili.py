"""
Bilibili 搜索引擎。

使用 Bilibili 搜索 API（无需 API key）。
中文视频教程、技术分享、知识区的最佳来源。
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

logger = logging.getLogger("scout.engines.bilibili")


class BilibiliEngine(Engine):
    """Bilibili 搜索引擎。"""

    name = "bilibili"
    needs_browser = False
    supports_freshness = True
    supports_safesearch = False

    # 排序方式
    _SORT_MAP = {
        None: 0,      # 综合排序
        "day": 2,     # 最新发布
        "week": 2,    # 最新发布
        "month": 1,   # 最多播放
        "year": 1,    # 最多播放
    }

    def build_url(
        self,
        query: str,
        max_results: int,
        filters: SearchFilters | None = None,
    ) -> str:
        """构建 Bilibili 搜索 API URL。

        端点：https://api.bilibili.com/x/web-interface/search/type
        """
        filters = filters or SearchFilters()

        params = {
            "search_type": "video",
            "keyword": query,
            "page": "1",
            "pagesize": str(min(max_results, 50)),
            "order": str(self._SORT_MAP.get(filters.freshness, 0)),
        }

        return f"https://api.bilibili.com/x/web-interface/search/type?{urllib.parse.urlencode(params)}"

    def parse(self, data: str) -> list[SearchResult]:
        """解析 Bilibili 搜索 API JSON 响应。"""
        results: list[SearchResult] = []

        try:
            payload = json.loads(data)
        except json.JSONDecodeError:
            logger.warning("Bilibili JSON 解析失败")
            return results

        if payload.get("code") != 0:
            logger.warning("Bilibili API 错误: %s", payload.get("message", ""))
            return results

        items = payload.get("data", {}).get("result", [])

        for item in items:
            title = item.get("title", "")
            bvid = item.get("bvid", "")
            aid = item.get("aid", 0)
            description = item.get("description", "")
            author = item.get("author", "")
            play_count = item.get("play", 0)
            danmaku = item.get("video_review", 0)  # 弹幕数
            duration = item.get("duration", "")
            pubdate = item.get("pubdate", 0)
            tag = item.get("tag", "")
            favorites = item.get("favorites", 0)

            if not bvid or not title:
                continue

            # 清理 HTML 标签
            import re
            title = re.sub(r'<[^>]+>', '', title)

            # 构建 URL
            url = f"https://www.bilibili.com/video/{bvid}"

            # 计算发布时间
            published_age = ""
            if pubdate:
                from datetime import datetime, timezone
                try:
                    created_dt = datetime.fromtimestamp(pubdate, tz=timezone.utc)
                    age = datetime.now(timezone.utc) - created_dt
                    if age.days > 365:
                        published_age = f"{age.days // 365} 年前"
                    elif age.days > 30:
                        published_age = f"{age.days // 30} 个月前"
                    elif age.days > 0:
                        published_age = f"{age.days} 天前"
                    else:
                        hours = age.seconds // 3600
                        published_age = f"{hours} 小时前" if hours > 0 else "刚刚"
                except (ValueError, OSError):
                    pass

            # 格式化播放量
            def format_count(count: int) -> str:
                if count >= 10000:
                    return f"{count / 10000:.1f}万"
                return str(count)

            # 构建摘要
            snippet_parts = []
            if author:
                snippet_parts.append(f"👤 {author}")
            if play_count:
                snippet_parts.append(f"👁 {format_count(play_count)}")
            if danmaku:
                snippet_parts.append(f"💬 {format_count(danmaku)}")
            if duration:
                snippet_parts.append(f"⏱ {duration}")
            if published_age:
                snippet_parts.append(f"📅 {published_age}")
            if tag:
                # 只取前几个标签
                tags = tag.split(",")[:3]
                snippet_parts.append(f"🏷️ {', '.join(tags)}")
            if description:
                desc_preview = description[:100]
                if len(description) > 100:
                    desc_preview += "..."
                snippet_parts.append(desc_preview)

            snippet = " | ".join(snippet_parts)

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
        """使用 aiohttp 抓取 Bilibili API。

        Bilibili 需要 Referer 头。
        """
        from ..config import settings
        from ..fetchers.http import _fetch_with_aiohttp

        headers = {
            "Referer": "https://www.bilibili.com",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }

        return await _fetch_with_aiohttp(url, settings.request_timeout, None, headers=headers)


# 注册引擎
register_engine(BilibiliEngine())
