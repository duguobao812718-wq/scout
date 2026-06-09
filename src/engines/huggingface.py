"""
HuggingFace 搜索引擎。

使用 HuggingFace Hub API（免费，无需 API key）。
AI 模型、数据集搜索的最佳来源。
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

logger = logging.getLogger("scout.engines.huggingface")


class HuggingFaceEngine(Engine):
    """HuggingFace 搜索引擎。"""

    name = "huggingface"
    needs_browser = False
    supports_freshness = True
    supports_safesearch = False

    # 搜索类型
    _SEARCH_TYPES = {
        "model": "https://huggingface.co/api/models",
        "dataset": "https://huggingface.co/api/datasets",
    }

    def build_url(
        self,
        query: str,
        max_results: int,
        filters: SearchFilters | None = None,
    ) -> str:
        """构建 HuggingFace 搜索 API URL。

        端点：https://huggingface.co/api/models 或 /datasets
        """
        filters = filters or SearchFilters()

        # 根据 category 决定搜索类型
        search_type = "model"
        if filters.category == "dataset":
            search_type = "dataset"

        params = {
            "search": query,
            "limit": str(min(max_results, 20)),
            "sort": "downloads",
            "direction": "-1",
        }

        # 新鲜度
        if filters.freshness:
            freshness_map = {
                "day": 1,
                "week": 7,
                "month": 30,
                "year": 365,
            }
            days = freshness_map.get(filters.freshness, 365)
            params["createdAfter"] = f"{days}d"

        base_url = self._SEARCH_TYPES.get(search_type, self._SEARCH_TYPES["model"])
        return f"{base_url}?{urllib.parse.urlencode(params)}"

    def parse(self, data: str) -> list[SearchResult]:
        """解析 HuggingFace API JSON 响应。"""
        results: list[SearchResult] = []

        try:
            payload = json.loads(data)
        except json.JSONDecodeError:
            logger.warning("HuggingFace JSON 解析失败")
            return results

        # API 返回的是数组
        items = payload if isinstance(payload, list) else payload.get("items", [])

        for item in items:
            model_id = item.get("id", "") or item.get("modelId", "")
            author = item.get("author", "")
            pipeline_tag = item.get("pipeline_tag", "")
            tags = item.get("tags", [])
            downloads = item.get("downloads", 0)
            likes = item.get("likes", 0)
            last_modified = item.get("lastModified", "") or item.get("last_modified", "")

            if not model_id:
                continue

            # 构建 URL
            url = f"https://huggingface.co/{model_id}"

            # 构建摘要
            snippet_parts = []
            if pipeline_tag:
                snippet_parts.append(f"Task: {pipeline_tag}")
            if author:
                snippet_parts.append(f"by {author}")
            if downloads:
                snippet_parts.append(f"⬇ {downloads:,}")
            if likes:
                snippet_parts.append(f"❤ {likes:,}")
            if tags:
                snippet_parts.append(f"Tags: {', '.join(tags[:5])}")
            if last_modified:
                snippet_parts.append(f"Updated: {last_modified[:10]}")

            snippet = " | ".join(snippet_parts)

            # 标题
            title = model_id
            if pipeline_tag:
                title = f"{model_id} - {pipeline_tag}"

            results.append(
                SearchResult(
                    title=title,
                    url=url,
                    snippet=snippet,
                    engine=self.name,
                    published_age=last_modified[:10] if last_modified else "",
                )
            )

        return results

    async def _fetch(self, url: str) -> str:
        """使用 aiohttp 抓取 HuggingFace JSON API。"""
        from ..config import settings
        from ..fetchers.http import _fetch_with_aiohttp

        return await _fetch_with_aiohttp(url, settings.request_timeout, None)


# 注册引擎
register_engine(HuggingFaceEngine())
