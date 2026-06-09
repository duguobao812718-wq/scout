"""
OpenStreetMap 地图搜索引擎。

使用 Nominatim API（免费，无需 API key）。
地点搜索、地址查询、POI 搜索的最佳来源。
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

logger = logging.getLogger("scout.engines.openstreetmap")


class OpenStreetMapEngine(Engine):
    """OpenStreetMap 地图搜索引擎。"""

    name = "openstreetmap"
    needs_browser = False
    supports_freshness = False
    supports_safesearch = False

    # 搜索类型
    _FEATURE_TYPES = {
        "default": "",           # 所有类型
        "country": "country",
        "state": "state",
        "city": "city",
        "settlement": "settlement",  # 城镇、村庄
        "poi": "poi",           # 兴趣点
    }

    def build_url(
        self,
        query: str,
        max_results: int,
        filters: SearchFilters | None = None,
    ) -> str:
        """构建 Nominatim 搜索 API URL。

        端点：https://nominatim.openstreetmap.org/search
        """
        filters = filters or SearchFilters()

        params = {
            "q": query,
            "format": "jsonv2",
            "limit": str(min(max_results, 50)),
            "addressdetails": "1",
            "extratags": "1",
            "namedetails": "1",
        }

        # 根据 category 设置 featureType
        if filters.category:
            feature_type = self._FEATURE_TYPES.get(filters.category, "")
            if feature_type:
                params["featureType"] = feature_type

        # 语言偏好
        params["accept-language"] = "zh-CN,en"

        return f"https://nominatim.openstreetmap.org/search?{urllib.parse.urlencode(params)}"

    def parse(self, data: str) -> list[SearchResult]:
        """解析 Nominatim API JSON 响应。"""
        results: list[SearchResult] = []

        try:
            items = json.loads(data)
        except json.JSONDecodeError:
            logger.warning("OpenStreetMap JSON 解析失败")
            return results

        if not isinstance(items, list):
            logger.warning("OpenStreetMap 响应格式错误")
            return results

        for item in items:
            place_id = item.get("place_id", "")
            name = item.get("name", "")
            display_name = item.get("display_name", "")
            osm_type = item.get("type", "")
            osm_id = item.get("osm_id", "")
            lat = item.get("lat", "")
            lon = item.get("lon", "")
            category = item.get("category", "")
            importance = item.get("importance", 0)
            address = item.get("address", {})
            extratags = item.get("extratags", {})
            namedetails = item.get("namedetails", {})

            if not display_name:
                continue

            # 构建 OpenStreetMap 页面 URL
            url = f"https://www.openstreetmap.org/{osm_type}/{osm_id}" if osm_type and osm_id else f"https://www.openstreetmap.org/?mlat={lat}&mlon={lon}"

            # 构建摘要
            snippet_parts = []

            # 类型信息
            type_display = self._get_type_display(osm_type, category)
            if type_display:
                snippet_parts.append(f"📍 {type_display}")

            # 坐标
            if lat and lon:
                snippet_parts.append(f"🌐 {lat}, {lon}")

            # 地址组件
            address_parts = []
            if address.get("city"):
                address_parts.append(address["city"])
            elif address.get("town"):
                address_parts.append(address["town"])
            elif address.get("village"):
                address_parts.append(address["village"])
            if address.get("state"):
                address_parts.append(address["state"])
            if address.get("country"):
                address_parts.append(address["country"])
            if address_parts:
                snippet_parts.append(f"📌 {', '.join(address_parts)}")

            # 额外信息
            extra_info = []
            if extratags.get("website"):
                extra_info.append(f"🌐 {extratags['website']}")
            if extratags.get("phone"):
                extra_info.append(f"📞 {extratags['phone']}")
            if extratags.get("opening_hours"):
                extra_info.append(f"🕐 {extratags['opening_hours']}")
            if extratags.get("wikipedia"):
                extra_info.append(f"📖 {extratags['wikipedia']}")
            if extra_info:
                snippet_parts.extend(extra_info[:3])  # 最多显示 3 个

            snippet = " | ".join(snippet_parts)

            # 标题
            title = name or display_name.split(",")[0] if display_name else "Unknown Place"

            results.append(
                SearchResult(
                    title=title,
                    url=url,
                    snippet=snippet,
                    engine=self.name,
                )
            )

        return results

    def _get_type_display(self, osm_type: str, category: str) -> str:
        """获取类型的中文显示名称。"""
        type_map = {
            "house": "房屋",
            "building": "建筑",
            "road": "道路",
            "highway": "公路",
            "railway": "铁路",
            "waterway": "水道",
            "natural": "自然地理",
            "landuse": "土地利用",
            "amenity": "公共设施",
            "shop": "商店",
            "tourism": "旅游景点",
            "leisure": "休闲娱乐",
            "historic": "历史遗迹",
            "man_made": "人工设施",
            "boundary": "边界",
            "place": "地名",
        }

        category_map = {
            "place": "地名",
            "boundary": "行政区划",
            "highway": "道路",
            "amenity": "设施",
            "shop": "商店",
            "tourism": "景点",
            "natural": "自然地理",
        }

        return type_map.get(osm_type) or category_map.get(category) or osm_type

    async def _fetch(self, url: str) -> str:
        """使用 aiohttp 抓取 Nominatim API。

        Nominatim 要求 User-Agent 头。
        """
        from ..config import settings
        from ..fetchers.http import _fetch_with_aiohttp

        headers = {
            "User-Agent": "Scout/1.0 (AI Agent Search Tool; https://github.com/duguobao812718-wq/scout)",
        }

        return await _fetch_with_aiohttp(url, settings.request_timeout, None, headers=headers)


# 注册引擎
register_engine(OpenStreetMapEngine())
