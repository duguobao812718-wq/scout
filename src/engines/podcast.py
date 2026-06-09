"""
Podcast 搜索引擎。

使用 iTunes Search API（免费，无需 API key）。
播客搜索的最佳来源。
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

logger = logging.getLogger("scout.engines.podcast")


class PodcastEngine(Engine):
    """Podcast 搜索引擎。"""

    name = "podcast"
    needs_browser = False
    supports_freshness = False
    supports_safesearch = False

    def build_url(
        self,
        query: str,
        max_results: int,
        filters: SearchFilters | None = None,
    ) -> str:
        """构建 iTunes Search API URL。

        端点：https://itunes.apple.com/search
        """
        params = {
            "term": query,
            "media": "podcast",
            "limit": str(min(max_results, 25)),
        }

        return f"https://itunes.apple.com/search?{urllib.parse.urlencode(params)}"

    def parse(self, data: str) -> list[SearchResult]:
        """解析 iTunes Search API JSON 响应。"""
        results: list[SearchResult] = []

        try:
            payload = json.loads(data)
        except json.JSONDecodeError:
            logger.warning("Podcast JSON 解析失败")
            return results

        items = payload.get("results", [])

        for item in items:
            track_name = item.get("trackName", "")
            artist_name = item.get("artistName", "")
            feed_url = item.get("feedUrl", "")
            track_view_url = item.get("trackViewUrl", "")
            artwork_url = item.get("artworkUrl100", "")
            genres = item.get("genres", [])
            track_count = item.get("trackCount", 0)
            release_date = item.get("releaseDate", "")
            content_advisory_rating = item.get("contentAdvisoryRating", "")

            if not track_name:
                continue

            # 优先使用 feed_url，如果没有则使用 track_view_url
            url = feed_url or track_view_url
            if not url:
                continue

            # 构建摘要
            snippet_parts = []
            if artist_name:
                snippet_parts.append(f"🎙️ {artist_name}")
            if genres:
                snippet_parts.append(f"🏷️ {', '.join(genres[:3])}")
            if track_count:
                snippet_parts.append(f"📻 {track_count} episodes")
            if release_date:
                snippet_parts.append(f"📅 {release_date[:10]}")
            if content_advisory_rating:
                snippet_parts.append(f"ℹ️ {content_advisory_rating}")

            snippet = " | ".join(snippet_parts)

            results.append(
                SearchResult(
                    title=track_name,
                    url=url,
                    snippet=snippet,
                    engine=self.name,
                    published_age=release_date[:10] if release_date else "",
                )
            )

        return results

    async def _fetch(self, url: str) -> str:
        """使用 aiohttp 抓取 iTunes API。"""
        from ..config import settings
        from ..fetchers.http import _fetch_with_aiohttp

        return await _fetch_with_aiohttp(url, settings.request_timeout, None)


# 注册引擎
register_engine(PodcastEngine())
