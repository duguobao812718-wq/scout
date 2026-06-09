"""
PubMed 搜索引擎。

使用 NCBI E-utilities API（免费，无需 API key，无反爬）。
生物医学文献最佳来源。
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

logger = logging.getLogger("scout.engines.pubmed")


class PubmedEngine(Engine):
    """PubMed 生物医学文献搜索引擎。"""

    name = "pubmed"
    needs_browser = False
    supports_freshness = True
    supports_safesearch = False

    def build_url(
        self,
        query: str,
        max_results: int,
        filters: SearchFilters | None = None,
    ) -> str:
        """构建 PubMed E-utilities URL。

        两步流程：
        1. esearch: 搜索 PMID 列表
        2. efetch: 获取摘要详情
        这里只构建 esearch URL，_fetch 中处理两步。
        """
        filters = filters or SearchFilters()

        # 添加日期过滤
        search_query = query
        if filters.freshness:
            from datetime import datetime, timedelta
            now = datetime.now()
            freshness_map = {
                "day": timedelta(days=1),
                "week": timedelta(weeks=1),
                "month": timedelta(days=30),
                "year": timedelta(days=365),
            }
            delta = freshness_map.get(filters.freshness, timedelta(days=365))
            from_date = (now - delta).strftime("%Y/%m/%d")
            search_query = f"{query} AND {from_date}:{now.strftime('%Y/%m/%d')}[dp]"

        params = {
            "db": "pubmed",
            "term": search_query,
            "retmax": str(min(max_results, 20)),
            "retmode": "json",
            "sort": "relevance",
        }

        return f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?{urllib.parse.urlencode(params)}"

    def parse(self, data: str) -> list[SearchResult]:
        """解析 PubMed esearch + efetch 结果。"""
        results: list[SearchResult] = []

        try:
            payload = json.loads(data)
        except json.JSONDecodeError:
            logger.warning("PubMed JSON 解析失败")
            return results

        articles = payload.get("articles", [])
        for article in articles:
            pmid = article.get("pmid", "")
            title = article.get("title", "")
            abstract = article.get("abstract", "")
            authors = article.get("authors", "")
            journal = article.get("journal", "")
            pub_date = article.get("pub_date", "")

            url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else ""

            # 构建摘要
            snippet_parts = []
            if authors:
                snippet_parts.append(authors[:100])
            if journal:
                snippet_parts.append(f"[{journal}]")
            if pub_date:
                snippet_parts.append(f"({pub_date})")
            if abstract:
                snippet_parts.append(abstract[:200])
            snippet = " ".join(snippet_parts)

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
        """两步流程：esearch 获取 PMID → efetch 获取详情。"""
        from ..config import settings
        from ..fetchers.http import _fetch_with_aiohttp

        # Step 1: esearch 获取 PMID 列表
        search_data = await _fetch_with_aiohttp(url, settings.request_timeout, None)

        try:
            search_result = json.loads(search_data)
            id_list = search_result.get("esearchresult", {}).get("idlist", [])
        except (json.JSONDecodeError, KeyError):
            return search_data

        if not id_list:
            return json.dumps({"articles": []})

        # Step 2: efetch 获取文章详情（XML 格式）
        ids = ",".join(id_list)
        efetch_url = (
            f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
            f"?db=pubmed&id={ids}&retmode=xml"
        )

        xml_data = await _fetch_with_aiohttp(efetch_url, settings.request_timeout, None)

        # 解析 XML
        articles = self._parse_xml(xml_data)
        return json.dumps({"articles": articles}, ensure_ascii=False)

    def _parse_xml(self, xml_data: str) -> list[dict]:
        """解析 PubMed efetch XML 响应。"""
        import defusedxml.ElementTree as DefusedET

        articles = []
        try:
            root = DefusedET.fromstring(xml_data)
        except Exception:
            return articles

        for article_el in root.findall(".//PubmedArticle"):
            pmid_el = article_el.find(".//PMID")
            title_el = article_el.find(".//ArticleTitle")
            abstract_el = article_el.find(".//AbstractText")
            journal_el = article_el.find(".//Title")

            # 作者
            authors = []
            for author_el in article_el.findall(".//Author"):
                last = author_el.findtext("LastName", "")
                first = author_el.findtext("ForeName", "")
                if last:
                    authors.append(f"{last} {first}".strip())

            # 发表日期
            pub_date_el = article_el.find(".//PubDate")
            pub_date = ""
            if pub_date_el is not None:
                year = pub_date_el.findtext("Year", "")
                month = pub_date_el.findtext("Month", "")
                pub_date = f"{year}-{month}" if year else ""

            pmid = pmid_el.text if pmid_el is not None else ""
            title = title_el.text if title_el is not None and title_el.text else ""
            abstract = abstract_el.text if abstract_el is not None and abstract_el.text else ""
            journal = journal_el.text if journal_el is not None and journal_el.text else ""

            articles.append({
                "pmid": pmid,
                "title": title.strip() if title else "",
                "abstract": abstract.strip()[:300] if abstract else "",
                "authors": ", ".join(authors[:3]),
                "journal": journal,
                "pub_date": pub_date,
            })

        return articles


# 注册引擎
register_engine(PubmedEngine())
