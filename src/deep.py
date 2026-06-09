"""
深度搜索模块。

多轮搜索：分解问题 → 搜索 → 聚合。
参考：MindSearch 的问题分解设计。
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger("scout.deep")


async def deep_search(
    question: str,
    max_rounds: int = 3,
    engines: list[str] | None = None,
    max_results_per_round: int = 5,
) -> dict[str, Any]:
    """深度搜索：多轮搜索 + 结果聚合。

    Args:
        question: 研究问题。
        max_rounds: 最大搜索轮数（1-5）。
        engines: 引擎名称列表。
        max_results_per_round: 每轮最大结果数。

    Returns:
        {
            "question": str,
            "sub_queries": list[str],
            "rounds": list[dict],
            "sources": list[dict],
            "tokens_estimated": int,
        }
    """
    from .server import _aggregate_search, _run_research
    from .formatting import estimate_tokens

    max_rounds = max(1, min(max_rounds, 5))

    # 第一轮：直接搜索
    logger.info("深度搜索第 1 轮: %s", question[:50])
    first_result = await _aggregate_search(
        question,
        engines=engines,
        max_results=max_results_per_round,
        use_cache=True,
    )

    all_sources = list(first_result.get("results", []))
    rounds = [{"query": question, "results": first_result.get("results", [])}]

    # 后续轮次：基于结果生成子查询
    if max_rounds > 1 and all_sources:
        sub_queries = _generate_sub_queries(question, all_sources)

        for i, sub_query in enumerate(sub_queries[:max_rounds - 1], 2):
            logger.info("深度搜索第 %d 轮: %s", i, sub_query[:50])

            round_result = await _aggregate_search(
                sub_query,
                engines=engines,
                max_results=max_results_per_round,
                use_cache=True,
            )

            round_results = round_result.get("results", [])
            rounds.append({"query": sub_query, "results": round_results})

            # 合并结果
            for r in round_results:
                if r["url"] not in {s["url"] for s in all_sources}:
                    all_sources.append(r)

    # 计算 token
    total_tokens = sum(estimate_tokens(s.get("snippet", "")) for s in all_sources)

    return {
        "question": question,
        "sub_queries": [r["query"] for r in rounds],
        "rounds": rounds,
        "sources": all_sources,
        "tokens_estimated": total_tokens,
    }


def _generate_sub_queries(question: str, sources: list[dict]) -> list[str]:
    """基于搜索结果生成子查询。

    策略：
    1. 从标题中提取关键词
    2. 生成更具体的查询
    """
    sub_queries = []

    # 提取关键词
    keywords = set()
    for source in sources[:5]:
        title = source.get("title", "")
        # 简单的关键词提取
        words = title.lower().split()
        for word in words:
            if len(word) > 3 and word not in {"the", "and", "for", "with"}:
                keywords.add(word)

    # 生成子查询
    keyword_list = list(keywords)[:3]
    for keyword in keyword_list:
        sub_queries.append(f"{question} {keyword}")

    return sub_queries


async def deep_research(
    question: str,
    max_rounds: int = 3,
    engines: list[str] | None = None,
    fetch: bool = True,
) -> dict[str, Any]:
    """深度研究：多轮搜索 + 页面抓取。

    Args:
        question: 研究问题。
        max_rounds: 最大搜索轮数。
        engines: 引擎名称列表。
        fetch: 是否抓取页面内容。

    Returns:
        {
            "question": str,
            "sub_queries": list[str],
            "sources": list[dict],
            "documents": list[dict],
            "tokens_estimated": int,
        }
    """
    from .fetchers.http import fetch_many

    # 深度搜索
    search_result = await deep_search(
        question,
        max_rounds=max_rounds,
        engines=engines,
    )

    sources = search_result.get("sources", [])
    documents = []
    total_tokens = search_result.get("tokens_estimated", 0)

    # 抓取页面内容
    if fetch and sources:
        urls = [s["url"] for s in sources[:5]]  # 限制抓取数量
        logger.info("抓取 %d 个页面...", len(urls))

        fetch_results = await fetch_many(urls)
        for i, result in enumerate(fetch_results):
            if not isinstance(result, Exception):
                documents.append(result)
                total_tokens += result.get("tokens_estimated", 0)

    return {
        "question": question,
        "sub_queries": search_result.get("sub_queries", []),
        "sources": sources,
        "documents": documents,
        "tokens_estimated": total_tokens,
    }
