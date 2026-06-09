"""
研究工具：搜索 + 抓取组合。

一次调用完成搜索和内容获取，返回搜索结果和抓取的页面内容。
参考：free-search-mcp 的 research.py 实现。
"""

from __future__ import annotations

import logging
from typing import Any

from .aggregator import aggregate_search
from .fetchers.http import fetch_many
from .formatting import estimate_tokens

logger = logging.getLogger("scout.research")


async def research(
    question: str,
    depth: int = 3,
    engines: list[str] | None = None,
    fetch: bool = True,
    use_cache: bool = True,
    max_age_seconds: int | None = None,
    page_max_age_seconds: int | None = None,
    freshness: str | None = None,
    include_domains: list[str] | None = None,
    exclude_domains: list[str] | None = None,
    category: str | None = None,
    include_text: str | None = None,
    exclude_text: str | None = None,
) -> dict[str, Any]:
    """研究工具：搜索 + 抓取。

    Args:
        question: 研究问题。
        depth: 抓取的搜索结果数量（1-8）。
        engines: 引擎名称列表。
        fetch: 是否抓取页面内容（False 则只返回搜索结果）。
        use_cache: 是否使用缓存。
        max_age_seconds: 搜索缓存最大年龄。
        page_max_age_seconds: 页面缓存最大年龄。
        freshness: "day"|"week"|"month"|"year"。
        include_domains: 限制域名列表。
        exclude_domains: 排除域名列表。
        category: "news"|"pdf"|"github"|"paper"|"forum"|"blog"。
        include_text: 标题/摘要必须包含的文本。
        exclude_text: 标题/摘要排除的文本。

    Returns:
        {
            "question": str,
            "engines": list[str],
            "sources": list[dict],  # 搜索结果
            "documents": list[dict],  # 抓取的页面内容
            "tokens_estimated": int,
            "errors": dict[str, str],
        }
    """
    if not question.strip():
        raise ValueError("question 不能为空")

    # 限制 depth
    depth = max(1, min(depth, 8))

    # 搜索
    search_result = await aggregate_search(
        question,
        engines=engines,
        max_results=depth,
        use_cache=use_cache,
        max_age_seconds=max_age_seconds,
        freshness=freshness,
        include_domains=include_domains,
        exclude_domains=exclude_domains,
        category=category,
        include_text=include_text,
        exclude_text=exclude_text,
    )

    sources = search_result.get("results", [])
    errors = search_result.get("errors", {})
    documents = []
    total_tokens = 0

    # 抓取页面内容
    if fetch and sources:
        urls = [s["url"] for s in sources[:depth]]
        logger.info("抓取 %d 个页面...", len(urls))

        fetch_results = await fetch_many(urls)

        for i, result in enumerate(fetch_results):
            if isinstance(result, Exception):
                logger.warning("抓取失败: %s (%s)", urls[i], result)
                errors[f"fetch_{i}"] = str(result)
            else:
                documents.append(result)
                total_tokens += result.get("tokens_estimated", 0)

    return {
        "question": question,
        "engines": search_result.get("engines", []),
        "sources": sources,
        "documents": documents,
        "tokens_estimated": total_tokens,
        "errors": errors,
    }
