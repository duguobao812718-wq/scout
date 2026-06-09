"""
YouTube 搜索引擎。

使用 YouTube RSS + 页面解析（无需 API key）。
视频教程、讲座、演示的最佳来源。
"""

from __future__ import annotations

import json
import logging
import re
import urllib.parse

from bs4 import BeautifulSoup

from . import (
    Engine,
    SearchFilters,
    SearchResult,
    register_engine,
)

logger = logging.getLogger("scout.engines.youtube")


class YouTubeEngine(Engine):
    """YouTube 搜索引擎。"""

    name = "youtube"
    needs_browser = False
    supports_freshness = True
    supports_safesearch = True

    # 排序方式
    _SORT_MAP = {
        "day": "upload_date",
        "week": "upload_date",
        "month": "view_count",
        "year": "view_count",
    }

    def build_url(
        self,
        query: str,
        max_results: int,
        filters: SearchFilters | None = None,
    ) -> str:
        """构建 YouTube 搜索 URL。

        使用 YouTube 搜索页面。
        """
        filters = filters or SearchFilters()

        params = {
            "search_query": query,
        }

        # 新鲜度
        if filters.freshness:
            freshness_map = {
                "day": "hour",      # 最近一小时
                "week": "today",    # 今天
                "month": "week",    # 本周
                "year": "month",    # 本月
            }
            params["sp"] = f"EgIIAQ%3D%3D"  # 按上传日期排序
            if filters.freshness in freshness_map:
                # 添加时间过滤
                time_filter = freshness_map[filters.freshness]
                if time_filter == "hour":
                    params["sp"] = "EgIIAQ%3D%3D"
                elif time_filter == "today":
                    params["sp"] = "EgIIAQ%3D%3D"
                elif time_filter == "week":
                    params["sp"] = "EgIIAQ%3D%3D"
                elif time_filter == "month":
                    params["sp"] = "EgIIAQ%3D%3D"

        return f"https://www.youtube.com/results?{urllib.parse.urlencode(params)}"

    def parse(self, html: str) -> list[SearchResult]:
        """解析 YouTube 搜索结果页面。"""
        results: list[SearchResult] = []

        # YouTube 搜索结果在 JSON 数据中
        # 提取 ytInitialData
        match = re.search(r'var ytInitialData = ({.*?});', html)
        if not match:
            logger.warning("无法提取 YouTube 初始数据")
            return results

        try:
            data = json.loads(match.group(1))
        except json.JSONDecodeError:
            logger.warning("YouTube JSON 解析失败")
            return results

        # 遍历搜索结果
        contents = data.get("contents", {}).get("twoColumnSearchResultsRenderer", {}).get("primaryContents", {}).get("sectionListRenderer", {}).get("contents", [])

        for section in contents:
            items = section.get("itemSectionRenderer", {}).get("contents", [])
            for item in items:
                video = item.get("videoRenderer", {})
                if not video:
                    continue

                video_id = video.get("videoId", "")
                title_runs = video.get("title", {}).get("runs", [])
                title = "".join(run.get("text", "") for run in title_runs)

                description_snippets = video.get("descriptionSnippet", {}).get("runs", [])
                description = "".join(run.get("text", "") for run in description_snippets)

                # 时长
                length_text = video.get("lengthText", {}).get("simpleText", "")

                # 观看次数
                view_count_text = video.get("viewCountText", {}).get("simpleText", "")

                # 上传时间
                published_time = video.get("publishedTimeText", {}).get("simpleText", "")

                # 频道名
                owner = video.get("ownerText", {}).get("runs", [])
                channel_name = owner[0].get("text", "") if owner else ""

                if not video_id or not title:
                    continue

                url = f"https://www.youtube.com/watch?v={video_id}"

                # 构建摘要
                snippet_parts = []
                if channel_name:
                    snippet_parts.append(f"👤 {channel_name}")
                if view_count_text:
                    snippet_parts.append(f"👁 {view_count_text}")
                if length_text:
                    snippet_parts.append(f"⏱ {length_text}")
                if published_time:
                    snippet_parts.append(f"📅 {published_time}")
                if description:
                    # 截取前 150 字符
                    desc_preview = description[:150]
                    if len(description) > 150:
                        desc_preview += "..."
                    snippet_parts.append(desc_preview)

                snippet = " | ".join(snippet_parts)

                results.append(
                    SearchResult(
                        title=title,
                        url=url,
                        snippet=snippet,
                        engine=self.name,
                        published_age=published_time,
                    )
                )

        return results


# 注册引擎
register_engine(YouTubeEngine())
