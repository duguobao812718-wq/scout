"""
结构化数据提取模块。

从网页中提取 JSON-LD、OpenGraph、Twitter Cards 等结构化数据。
参考：free-search-mcp 的 structured.py 实现。
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

from bs4 import BeautifulSoup

logger = logging.getLogger("scout.structured")


async def extract_structured(url: str) -> dict[str, Any]:
    """从 URL 提取结构化数据。

    Returns:
        {
            "url": str,
            "json_ld": list[dict],
            "opengraph": dict,
            "twitter_card": dict,
            "microdata": list[dict],
        }
    """
    from .fetchers.http import fetch_html

    html = await fetch_html(url)
    return await asyncio.to_thread(_extract_sync, url, html)


def _extract_sync(url: str, html: str) -> dict[str, Any]:
    """同步提取结构化数据。"""
    soup = BeautifulSoup(html, "lxml")

    return {
        "url": url,
        "json_ld": _extract_json_ld(soup),
        "opengraph": _extract_opengraph(soup),
        "twitter_card": _extract_twitter_card(soup),
        "microdata": _extract_microdata(soup),
    }


def _extract_json_ld(soup: BeautifulSoup) -> list[dict]:
    """提取 JSON-LD 数据。"""
    results = []

    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string)
            if isinstance(data, list):
                results.extend(data)
            elif isinstance(data, dict):
                results.append(data)
        except (json.JSONDecodeError, TypeError):
            continue

    return results


def _extract_opengraph(soup: BeautifulSoup) -> dict[str, str]:
    """提取 OpenGraph 数据。"""
    og_data = {}

    for meta in soup.find_all("meta", property=re.compile(r"^og:")):
        prop = meta.get("property", "")
        content = meta.get("content", "")
        if prop and content:
            # 移除 og: 前缀
            key = prop[3:]
            og_data[key] = content

    return og_data


def _extract_twitter_card(soup: BeautifulSoup) -> dict[str, str]:
    """提取 Twitter Cards 数据。"""
    twitter_data = {}

    for meta in soup.find_all("meta", attrs={"name": re.compile(r"^twitter:")}):
        name = meta.get("name", "")
        content = meta.get("content", "")
        if name and content:
            # 移除 twitter: 前缀
            key = name[8:]
            twitter_data[key] = content

    return twitter_data


def _extract_microdata(soup: BeautifulSoup) -> list[dict]:
    """提取 Microdata 数据。"""
    results = []

    # 查找 itemscope 元素
    for item in soup.find_all(attrs={"itemscope": True}):
        item_data = {
            "type": item.get("itemtype", ""),
            "properties": {},
        }

        # 查找 itemprop 元素
        for prop in item.find_all(attrs={"itemprop": True}):
            name = prop.get("itemprop", "")
            value = _get_microdata_value(prop)
            if name and value:
                item_data["properties"][name] = value

        if item_data["properties"]:
            results.append(item_data)

    return results


def _get_microdata_value(element) -> str:
    """获取 microdata 元素的值。"""
    # 检查常见属性
    for attr in ["content", "src", "href", "datetime", "value"]:
        value = element.get(attr)
        if value:
            return value

    # 使用文本内容
    return element.get_text(strip=True)
