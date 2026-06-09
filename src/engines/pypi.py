"""
PyPI 搜索引擎。

使用 PyPI JSON API（免费，无需 API key）。
Python 包搜索的最佳来源。
"""

from __future__ import annotations

import logging
import urllib.parse

from . import (
    Engine,
    SearchFilters,
    SearchResult,
    register_engine,
)

logger = logging.getLogger("scout.engines.pypi")


class PyPIEngine(Engine):
    """PyPI 搜索引擎。"""

    name = "pypi"
    needs_browser = False
    supports_freshness = False
    supports_safesearch = False

    # PyPI 没有官方搜索 API，使用 Google Custom Search 的 site:pypi.org 限定
    # 或者使用 pypi.org 的简单搜索页面
    _SEARCH_URL = "https://pypi.org/search/"

    def build_url(
        self,
        query: str,
        max_results: int,
        filters: SearchFilters | None = None,
    ) -> str:
        """构建 PyPI 搜索 URL。

        使用 PyPI 搜索页面。
        """
        params = {
            "q": query,
        }

        return f"{self._SEARCH_URL}?{urllib.parse.urlencode(params)}"

    def parse(self, html: str) -> list[SearchResult]:
        """解析 PyPI 搜索结果页面。"""
        from bs4 import BeautifulSoup

        results: list[SearchResult] = []

        soup = BeautifulSoup(html, "html.parser")

        # PyPI 搜索结果在 <a> 标签中，class 包含 "package-snippet"
        package_snippets = soup.find_all("a", class_="package-snippet")

        for snippet in package_snippets:
            # 提取包名
            name_elem = snippet.find("span", class_="package-snippet__name")
            version_elem = snippet.find("span", class_="package-snippet__version")
            description_elem = snippet.find("p", class_="package-snippet__description")
            created_elem = snippet.find("span", class_="package-snippet__created")

            name = name_elem.get_text(strip=True) if name_elem else ""
            version = version_elem.get_text(strip=True) if version_elem else ""
            description = description_elem.get_text(strip=True) if description_elem else ""
            created = created_elem.get_text(strip=True) if created_elem else ""

            if not name:
                continue

            # 构建 URL
            url = f"https://pypi.org/project/{name}/"

            # 构建摘要
            snippet_parts = []
            if description:
                snippet_parts.append(description)
            if version:
                snippet_parts.append(f"v{version}")
            if created:
                snippet_parts.append(f"Updated: {created}")

            snippet_text = " | ".join(snippet_parts)

            results.append(
                SearchResult(
                    title=f"{name} - {description}" if description else name,
                    url=url,
                    snippet=snippet_text,
                    engine=self.name,
                    published_age=created,
                )
            )

        return results


# 注册引擎
register_engine(PyPIEngine())
