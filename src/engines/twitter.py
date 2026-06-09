"""
Twitter/X 搜索引擎。

使用 Nitter 实例（开源 Twitter 前端，免费，无需 API key）。
实时舆情、技术动态、人物观点的最佳来源。
"""

from __future__ import annotations

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

logger = logging.getLogger("scout.engines.twitter")

# Nitter 实例列表（公共实例，可能需要轮换）
_NITTER_INSTANCES = [
    "https://nitter.privacydev.net",
    "https://nitter.poast.org",
    "https://nitter.cz",
]


class TwitterEngine(Engine):
    """Twitter/X 搜索引擎（通过 Nitter）。"""

    name = "twitter"
    needs_browser = False
    supports_freshness = True
    supports_safesearch = False

    def build_url(
        self,
        query: str,
        max_results: int,
        filters: SearchFilters | None = None,
    ) -> str:
        """构建 Nitter 搜索 URL。

        使用第一个可用的 Nitter 实例。
        """
        filters = filters or SearchFilters()

        params = {
            "q": query,
        }

        # 新鲜度
        if filters.freshness:
            freshness_map = {
                "day": "24h",
                "week": "1w",
                "month": "1m",
                "year": "1y",
            }
            params["since"] = freshness_map.get(filters.freshness, "")

        # 使用第一个实例
        instance = _NITTER_INSTANCES[0]
        return f"{instance}/search?{urllib.parse.urlencode(params)}"

    def parse(self, html: str) -> list[SearchResult]:
        """解析 Nitter 搜索结果页面。"""
        results: list[SearchResult] = []

        soup = BeautifulSoup(html, "html.parser")

        # Nitter 搜索结果在 <div class="timeline-item"> 中
        timeline_items = soup.find_all("div", class_="timeline-item")

        for item in timeline_items:
            # 提取用户名和昵称
            username_elem = item.find("a", class_="username")
            fullname_elem = item.find("a", class_="fullname")

            username = username_elem.get_text(strip=True) if username_elem else ""
            fullname = fullname_elem.get_text(strip=True) if fullname_elem else ""

            # 提取推文内容
            content_elem = item.find("div", class_="tweet-content")
            content = content_elem.get_text(strip=True) if content_elem else ""

            # 提取时间
            time_elem = item.find("span", class_="tweet-date")
            time_text = time_elem.get_text(strip=True) if time_elem else ""

            # 提取链接
            link_elem = item.find("a", class_="tweet-link")
            if not link_elem:
                # 尝试其他方式找到链接
                link_elem = item.find("a", href=re.compile(r"^/[^/]+/status/\d+"))

            if not link_elem:
                continue

            href = link_elem.get("href", "")
            if not href:
                continue

            # 构建完整 URL
            url = f"https://twitter.com{href}" if href.startswith("/") else href

            # 提取统计数据
            stats = item.find_all("span", class_="tweet-stat")
            stat_parts = []
            for stat in stats:
                icon = stat.find("span", class_="icon-container")
                count = stat.get_text(strip=True)
                if icon and count:
                    stat_parts.append(count)

            # 构建摘要
            snippet_parts = []
            if fullname:
                snippet_parts.append(fullname)
            if username:
                snippet_parts.append(f"@{username}")
            if content:
                # 截取前 200 字符
                content_preview = content[:200]
                if len(content) > 200:
                    content_preview += "..."
                snippet_parts.append(content_preview)
            if stat_parts:
                snippet_parts.append(" | ".join(stat_parts))
            if time_text:
                snippet_parts.append(f"📅 {time_text}")

            snippet = " | ".join(snippet_parts)

            # 标题
            title = f"@{username}" if username else "Tweet"
            if content:
                title = content[:100] + ("..." if len(content) > 100 else "")

            results.append(
                SearchResult(
                    title=title,
                    url=url,
                    snippet=snippet,
                    engine=self.name,
                    published_age=time_text,
                )
            )

        return results


# 注册引擎
register_engine(TwitterEngine())
