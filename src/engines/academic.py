"""
学术搜索引擎。

使用 Semantic Scholar API（免费，无需 API key）获取学术论文。
补充 arXiv 搜索覆盖预印本。
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

logger = logging.getLogger("scout.engines.academic")


class SemanticScholarEngine(Engine):
    """Semantic Scholar 学术搜索引擎。"""

    name = "semantic_scholar"
    needs_browser = False
    supports_freshness = False
    supports_safesearch = False

    def build_url(
        self,
        query: str,
        max_results: int,
        filters: SearchFilters | None = None,
    ) -> str:
        """构建 Semantic Scholar API URL。

        端点：https://api.semanticscholar.org/graph/v1/paper/search
        """
        params = {
            "query": query,
            "limit": str(min(max_results, 100)),
            "fields": "title,url,abstract,year,citationCount,authors,venue,publicationDate",
        }

        # 年份过滤（通过 year 参数）
        filters = filters or SearchFilters()
        if filters.freshness:
            from datetime import datetime
            year = datetime.now().year
            year_map = {"day": year, "week": year, "month": year, "year": year - 1}
            params["year"] = str(year_map.get(filters.freshness, year))

        return f"https://api.semanticscholar.org/graph/v1/paper/search?{urllib.parse.urlencode(params)}"

    def parse(self, data: str) -> list[SearchResult]:
        """解析 Semantic Scholar JSON 响应。"""
        results: list[SearchResult] = []

        try:
            payload = json.loads(data)
        except json.JSONDecodeError:
            logger.warning("Semantic Scholar JSON 解析失败")
            return results

        papers = payload.get("data", [])

        for paper in papers:
            title = paper.get("title", "")
            paper_id = paper.get("paperId", "")
            abstract = paper.get("abstract", "") or ""
            year = paper.get("year", "")
            venue = paper.get("venue", "")
            citations = paper.get("citationCount", 0)
            authors = paper.get("authors", [])

            # 构建 URL
            url = f"https://www.semanticscholar.org/paper/{paper_id}" if paper_id else ""

            # 构建摘要
            snippet = abstract[:300] if abstract else ""
            if year:
                snippet = f"({year}) {snippet}"
            if venue:
                snippet = f"[{venue}] {snippet}"
            if citations:
                snippet = f"引用: {citations} | {snippet}"

            # 作者
            author_names = [a.get("name", "") for a in authors[:3]]
            if author_names:
                snippet = f"作者: {', '.join(author_names)} | {snippet}"

            if title and url:
                results.append(
                    SearchResult(
                        title=title,
                        url=url,
                        snippet=snippet,
                        engine=self.name,
                    )
                )

        return results

    async def _fetch(self, url: str) -> str:
        """使用 aiohttp 抓取 JSON API。"""
        from ..fetchers.http import _fetch_with_aiohttp
        from ..config import settings

        return await _fetch_with_aiohttp(url, settings.request_timeout, None)


class ArxivEngine(Engine):
    """arXiv 预印本搜索引擎。"""

    name = "arxiv"
    needs_browser = False
    supports_freshness = False
    supports_safesearch = False

    def build_url(
        self,
        query: str,
        max_results: int,
        filters: SearchFilters | None = None,
    ) -> str:
        """构建 arXiv API URL。

        端点：http://export.arxiv.org/api/query
        """
        # arXiv 使用自己的查询语法
        search_query = f"all:{query}"

        params = {
            "search_query": search_query,
            "start": "0",
            "max_results": str(min(max_results, 50)),
            "sortBy": "relevance",
            "sortOrder": "descending",
        }

        return f"https://export.arxiv.org/api/query?{urllib.parse.urlencode(params)}"

    def parse(self, data: str) -> list[SearchResult]:
        """解析 arXiv Atom XML 响应。"""
        import xml.etree.ElementTree as ET

        import defusedxml.ElementTree as DefusedET

        results: list[SearchResult] = []

        try:
            root = DefusedET.fromstring(data)
        except (ET.ParseError, DefusedET.EntitiesForbidden):
            logger.warning("arXiv XML 解析失败")
            return results

        # Atom 命名空间
        ns = {"atom": "http://www.w3.org/2005/Atom"}

        entries = root.findall("atom:entry", ns)

        for entry in entries:
            title_el = entry.find("atom:title", ns)
            summary_el = entry.find("atom:summary", ns)
            link_el = entry.find("atom:link[@type='text/html']", ns)
            published_el = entry.find("atom:published", ns)

            title = title_el.text.strip().replace("\n", " ") if title_el is not None and title_el.text else ""
            summary = summary_el.text.strip().replace("\n", " ")[:300] if summary_el is not None and summary_el.text else ""
            url = link_el.get("href", "") if link_el is not None else ""
            published = published_el.text[:10] if published_el is not None and published_el.text else ""

            # 提取作者
            authors = entry.findall("atom:author", ns)
            author_names = []
            for author in authors[:3]:
                name_el = author.find("atom:name", ns)
                if name_el is not None and name_el.text:
                    author_names.append(name_el.text.strip())

            # 构建摘要
            snippet = summary
            if author_names:
                snippet = f"作者: {', '.join(author_names)} | {snippet}"
            if published:
                snippet = f"({published}) {snippet}"

            # 提取 arXiv ID 作为 URL
            if not url:
                id_el = entry.find("atom:id", ns)
                if id_el is not None and id_el.text:
                    url = id_el.text

            if title and url:
                results.append(
                    SearchResult(
                        title=title,
                        url=url,
                        snippet=snippet,
                        engine=self.name,
                    )
                )

        return results

    async def _fetch(self, url: str) -> str:
        """使用 aiohttp 抓取 XML API。"""
        from ..fetchers.http import _fetch_with_aiohttp
        from ..config import settings

        return await _fetch_with_aiohttp(url, settings.request_timeout, None)


# 注册引擎
register_engine(SemanticScholarEngine())
register_engine(ArxivEngine())
