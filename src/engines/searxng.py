"""
SearXNG 元搜索引擎。

SearXNG 是开源元搜索引擎，聚合 Google/Bing/DuckDuckGo 等多个后端。
公共实例禁用了 JSON API，使用 HTML 解析。

策略：并发竞速多个公共实例，第一个返回非空结果的获胜。
使用 curl_cffi 浏览器指纹绕过反爬。
"""

from __future__ import annotations

import asyncio
import logging
import random
import urllib.parse
from typing import Any

from ..utils import normalize_url
from . import (
    Engine,
    SearchFilters,
    SearchResult,
    extract_date_hint,
    parse_html,
    register_engine,
    text_of,
)

logger = logging.getLogger("scout.engines.searxng")

# 默认公共 SearXNG 实例（2026-06 验证可用）
_DEFAULT_INSTANCES: list[str] = [
    "https://search.inetol.net",
    "https://baresearch.org",
    "https://searx.tiekoetter.com",
    "https://opnxng.com",
    "https://search.rhscz.eu",
]


def _get_instances() -> list[str]:
    """获取 SearXNG 实例列表（支持通过 SCOUT_SEARXNG_INSTANCES 环境变量配置）。"""
    from ..config import settings
    if settings.searxng_instances:
        return settings.searxng_instances
    return _DEFAULT_INSTANCES

# 每个实例的超时时间
_INSTANCE_TIMEOUT = 8.0

# 每批竞速实例数
_RACE_BATCH = 3


class SearxNGEngine(Engine):
    """SearXNG 元搜索引擎。"""

    name = "searxng"
    needs_browser = False
    supports_freshness = True
    supports_safesearch = False  # SearXNG 的 safesearch 由实例配置决定

    def build_url(
        self,
        query: str,
        max_results: int,
        filters: SearchFilters | None = None,
    ) -> str:
        """构建 SearXNG 搜索 URL（使用第一个实例作为默认）。"""
        return self._build_instance_url(_get_instances()[0], query, filters)

    def _build_instance_url(
        self,
        instance: str,
        query: str,
        filters: SearchFilters | None = None,
        category: str | None = None,
    ) -> str:
        """为指定实例构建搜索 URL。"""
        filters = filters or SearchFilters()

        q = query
        if filters.include_domains:
            for domain in filters.include_domains:
                q = f"{q} site:{domain}"

        params = {"q": q}

        # 分类（general / images / news / science）
        if category:
            params["categories"] = category

        # 新鲜度
        if filters.freshness:
            freshness_map = {"day": "day", "week": "week", "month": "month", "year": "year"}
            fv = freshness_map.get(filters.freshness)
            if fv:
                params["time_range"] = fv

        # 区域
        from ..config import settings

        if settings.region:
            params["language"] = settings.region.split("-")[0] if "-" in settings.region else settings.region

        base = instance.rstrip("/")
        return f"{base}/search?{urllib.parse.urlencode(params)}"

    def parse(self, html: str) -> list[SearchResult]:
        """解析 SearXNG HTML 搜索结果。"""
        soup = parse_html(html)
        results: list[SearchResult] = []
        seen_urls: set[str] = set()

        # SearXNG 使用 article.result 容器
        articles = soup.select("article.result")
        if not articles:
            # 备用选择器
            articles = soup.select("div.result, div.results .result")

        for art in articles:
            # 跳过广告
            classes = " ".join(art.get("class", []))
            if "result-ad" in classes or "result-ad" in art.get("id", ""):
                continue

            # 标题和链接
            link = art.select_one("h3 a, a.url_header")
            if not link:
                link = art.select_one("a[href]")
                if not link:
                    continue

            title = text_of(link)
            url = link.get("href", "")

            if not url or not title:
                continue

            # 处理相对 URL
            if url.startswith("//"):
                url = "https:" + url
            elif url.startswith("/"):
                url = "https://yandex.com" + url  # fallback，通常不会出现

            if not url.startswith("http"):
                continue

            # 归一化去重
            normalized = normalize_url(url)
            if normalized in seen_urls:
                continue
            seen_urls.add(normalized)

            # 摘要
            snippet = ""
            snippet_el = art.select_one("p.content, p.result-content, .content")
            if snippet_el:
                snippet = text_of(snippet_el)

            # 日期提示
            date_text = extract_date_hint(snippet) or extract_date_hint(title)

            if title and url:
                results.append(
                    SearchResult(
                        title=title,
                        url=url,
                        snippet=snippet,
                        engine=self.name,
                        published_age=date_text,
                    )
                )

        return results

    async def _fetch_instance(
        self,
        instance: str,
        query: str,
        filters: SearchFilters | None,
        category: str | None = None,
    ) -> list[SearchResult]:
        """抓取单个实例。失败时返回空列表，不抛异常。"""
        from ..fetchers.http import fetch_html

        url = self._build_instance_url(instance, query, filters, category=category)
        try:
            html = await fetch_html(url, timeout=_INSTANCE_TIMEOUT, engine="searxng")
            return self.parse(html)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.debug("SearXNG 实例 %s 失败: %s", instance, e)
            return []

    async def search(
        self,
        query: str,
        max_results: int = 10,
        filters: SearchFilters | None = None,
        diagnostics: dict | None = None,
        max_retries: int = 0,  # SearXNG 自己处理重试（多实例竞速）
    ) -> list[SearchResult]:
        """并发竞速多个实例，第一个返回非空结果的获胜。"""
        filters = filters or SearchFilters()

        # 随机打乱实例顺序，分散负载
        instances = list(_get_instances())
        random.shuffle(instances)

        results: list[SearchResult] = []

        # 分批竞速
        for start in range(0, len(instances), _RACE_BATCH):
            batch = instances[start:start + _RACE_BATCH]
            tasks = [
                asyncio.ensure_future(self._fetch_instance(inst, query, filters))
                for inst in batch
            ]
            try:
                for fut in asyncio.as_completed(tasks):
                    try:
                        parsed = await fut
                    except Exception:
                        continue
                    if parsed:
                        results = parsed
                        break
            finally:
                for t in tasks:
                    if not t.done():
                        t.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
            if results:
                break

        # 后过滤
        from . import apply_post_filters
        results = apply_post_filters(results, filters)

        # 设置 rank
        for i, r in enumerate(results):
            r.rank = i + 1
            r.engine = self.name

        if diagnostics is not None:
            diagnostics.setdefault(self.name, {})["count"] = len(results)

        return results[:max_results]

    async def search_images(
        self,
        query: str,
        max_results: int = 10,
        filters: SearchFilters | None = None,
    ) -> list[dict[str, Any]]:
        """图片搜索。返回包含图片 URL 的字典列表。"""
        filters = filters or SearchFilters()

        instances = list(_get_instances())
        random.shuffle(instances)

        for start in range(0, len(instances), _RACE_BATCH):
            batch = instances[start:start + _RACE_BATCH]
            tasks = [
                asyncio.ensure_future(self._fetch_instance_images(inst, query, filters))
                for inst in batch
            ]
            try:
                for fut in asyncio.as_completed(tasks):
                    try:
                        parsed = await fut
                    except Exception:
                        continue
                    if parsed:
                        return parsed[:max_results]
            finally:
                for t in tasks:
                    if not t.done():
                        t.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)

        return []

    async def _fetch_instance_images(
        self,
        instance: str,
        query: str,
        filters: SearchFilters | None,
    ) -> list[dict[str, Any]]:
        """抓取单个实例的图片搜索结果。"""
        from ..fetchers.http import fetch_html

        url = self._build_instance_url(instance, query, filters, category="images")
        try:
            html = await fetch_html(url, timeout=_INSTANCE_TIMEOUT, engine="searxng")
            return self._parse_images(html)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.debug("SearXNG 图片搜索实例 %s 失败: %s", instance, e)
            return []

    def _parse_images(self, html: str) -> list[dict[str, Any]]:
        """解析 SearXNG 图片搜索结果。"""
        soup = parse_html(html)
        results = []

        # SearXNG 图片结果使用不同的结构
        articles = soup.select("article.result, div.result")

        for art in articles:
            classes = " ".join(art.get("class", []))
            if "result-ad" in classes:
                continue

            # 图片链接通常在 a 标签中
            link = art.select_one("a[href]")
            if not link:
                continue

            # 图片源 URL（SearXNG 将图片 URL 放在 data-src 或 img src 中）
            img = art.select_one("img")
            if not img:
                continue

            img_src = img.get("data-src") or img.get("src", "")
            if not img_src or img_src.startswith("data:"):
                continue

            title = text_of(link) or img.get("alt", "")
            page_url = link.get("href", "")

            # 提取图片尺寸（如果有）
            width = img.get("width", "")
            height = img.get("height", "")

            results.append({
                "title": title,
                "url": page_url,
                "image_url": img_src,
                "width": width,
                "height": height,
            })

        return results


# 注册引擎
register_engine(SearxNGEngine())
