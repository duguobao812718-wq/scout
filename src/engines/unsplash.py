"""
Unsplash 图片搜索引擎。

使用 Unsplash API（无需 API key，有限制）。
高质量免费图片的最佳来源。
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

logger = logging.getLogger("scout.engines.unsplash")


class UnsplashEngine(Engine):
    """Unsplash 图片搜索引擎。"""

    name = "unsplash"
    needs_browser = False
    supports_freshness = False
    supports_safesearch = True

    def build_url(
        self,
        query: str,
        max_results: int,
        filters: SearchFilters | None = None,
    ) -> str:
        """构建 Unsplash 搜索 URL。

        使用 Unsplash 搜索页面（无需 API key）。
        """
        params = {
            "query": query,
        }

        return f"https://unsplash.com/s/photos/{urllib.parse.quote(query)}"

    def parse(self, html: str) -> list[SearchResult]:
        """解析 Unsplash 搜索结果页面。"""
        results: list[SearchResult] = []

        # Unsplash 使用 JSON 数据嵌入在页面中
        import re

        # 提取 JSON 数据
        match = re.search(r'window\.__INITIAL_STATE__\s*=\s*({.*?});', html, re.DOTALL)
        if not match:
            # 尝试另一种模式
            match = re.search(r'"photos":\s*(\[.*?\])', html, re.DOTALL)

        if match:
            try:
                data = json.loads(match.group(1))
                # 解析图片数据
                if isinstance(data, dict):
                    photos = data.get("photos", {}).get("data", [])
                else:
                    photos = data

                for photo in photos[:20]:  # 限制最多 20 个
                    photo_id = photo.get("id", "")
                    description = photo.get("description", "") or photo.get("alt_description", "")
                    user = photo.get("user", {})
                    username = user.get("username", "")
                    name = user.get("name", "")
                    urls = photo.get("urls", {})
                    regular_url = urls.get("regular", "")
                    likes = photo.get("likes", 0)
                    created_at = photo.get("created_at", "")

                    if not photo_id:
                        continue

                    # 构建页面 URL
                    url = f"https://unsplash.com/photos/{photo_id}"

                    # 构建摘要
                    snippet_parts = []
                    if name:
                        snippet_parts.append(f"📷 {name} (@{username})")
                    if description:
                        snippet_parts.append(description[:100])
                    if likes:
                        snippet_parts.append(f"❤️ {likes}")
                    if created_at:
                        snippet_parts.append(f"📅 {created_at[:10]}")

                    snippet = " | ".join(snippet_parts)

                    title = description or f"Photo by {name}" or f"Unsplash Photo {photo_id}"

                    results.append(
                        SearchResult(
                            title=title,
                            url=url,
                            snippet=snippet,
                            engine=self.name,
                        )
                    )

                return results
            except json.JSONDecodeError:
                pass

        # 如果 JSON 解析失败，使用 HTML 解析
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")

        # 查找图片元素
        figures = soup.find_all("figure")

        for figure in figures[:20]:
            img = figure.find("img")
            link = figure.find("a")

            if not img or not link:
                continue

            src = img.get("src", "") or img.get("data-src", "")
            alt = img.get("alt", "")
            href = link.get("href", "")

            if not href:
                continue

            url = f"https://unsplash.com{href}" if href.startswith("/") else href

            # 构建摘要
            snippet_parts = []
            if alt:
                snippet_parts.append(alt)
            if src:
                snippet_parts.append(f"🖼️ {src[:50]}...")

            snippet = " | ".join(snippet_parts) if snippet_parts else ""

            results.append(
                SearchResult(
                    title=alt or f"Unsplash Photo",
                    url=url,
                    snippet=snippet,
                    engine=self.name,
                )
            )

        return results


# 注册引擎
register_engine(UnsplashEngine())
