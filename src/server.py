"""
Scout MCP 服务器入口。

使用 FastMCP 框架，注册搜索工具供 AI Agent 调用。
所有核心逻辑直接内联，避免模块间导入死锁。
"""

import asyncio
import hashlib
import json
import logging
import time
from typing import Any, Literal
from urllib.parse import urlparse

from mcp.server.fastmcp import Context, FastMCP
from mcp.types import ToolAnnotations

from .cache import cache
from .config import settings
from .engines import SearchFilters, SearchResult, get_engine, list_engines as _list_engines
from .fetchers.http import fetch_many, fetch_page
from .formatting import (
    errors_to_hint,
    estimate_tokens,
    render_fetch,
    render_research,
    render_search,
    smart_truncate,
)
from .ratelimit import get_limiter

# 配置日志
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("scout")

# 创建 MCP 服务器实例
mcp = FastMCP("scout")

# 格式类型
Format = Literal["markdown", "json"]

# RRF 常数
_RRF_K = 60.0


# ── 内联聚合器 ────────────────────────────────────────────


def _merge_rrf(
    results_by_engine: dict[str, list[SearchResult]],
    max_results: int,
) -> list[dict[str, Any]]:
    """Reciprocal Rank Fusion 合并。"""
    url_scores: dict[str, float] = {}
    url_info: dict[str, dict[str, Any]] = {}

    for engine_name, results in results_by_engine.items():
        for rank, result in enumerate(results, 1):
            url = result.url
            score = 1.0 / (_RRF_K + rank)
            url_scores[url] = url_scores.get(url, 0) + score

            if url not in url_info:
                url_info[url] = {
                    "title": result.title,
                    "url": result.url,
                    "snippet": result.snippet,
                    "engines": [],
                    "published_age": result.published_age,
                }
            url_info[url]["engines"].append(engine_name)
            if len(result.snippet) > len(url_info[url]["snippet"]):
                url_info[url]["snippet"] = result.snippet

    sorted_urls = sorted(url_scores.keys(), key=lambda u: url_scores[u], reverse=True)

    seen_hosts: dict[str, set[str]] = {}
    merged = []
    for url in sorted_urls:
        info = url_info[url]
        host = urlparse(url).hostname or ""
        title = info["title"]
        if host in seen_hosts:
            title_tokens = set(title.lower().split())
            for seen in seen_hosts[host]:
                seen_tokens = set(seen.lower().split())
                if title_tokens and seen_tokens:
                    overlap = len(title_tokens & seen_tokens)
                    min_len = min(len(title_tokens), len(seen_tokens))
                    if min_len > 0 and overlap / min_len > 0.8:
                        break
            else:
                seen_hosts[host].add(title.lower())
                merged.append({
                    "title": info["title"],
                    "url": info["url"],
                    "snippet": info["snippet"],
                    "engines": info["engines"],
                    "score": url_scores[url],
                    "published_age": info["published_age"],
                })
        else:
            seen_hosts[host] = {title.lower()}
            merged.append({
                "title": info["title"],
                "url": info["url"],
                "snippet": info["snippet"],
                "engines": info["engines"],
                "score": url_scores[url],
                "published_age": info["published_age"],
            })
        if len(merged) >= max_results:
            break

    return merged


async def _aggregate_search(
    query: str,
    engines: list[str] | None = None,
    max_results: int = 10,
    use_cache: bool = True,
    max_age_seconds: int | None = None,
    freshness: str | None = None,
    include_domains: list[str] | None = None,
    exclude_domains: list[str] | None = None,
    category: str | None = None,
    include_text: str | None = None,
    exclude_text: str | None = None,
) -> dict[str, Any]:
    """多引擎并发搜索 + RRF 合并。"""
    if engines is None:
        engines = settings.default_engines

    valid_engines = []
    for name in engines:
        try:
            get_engine(name)
            valid_engines.append(name)
        except ValueError:
            logger.warning("跳过未知引擎: %s", name)

    if not valid_engines:
        return {"query": query, "engines": [], "results": [], "cached": False, "errors": {"all": "无可用引擎"}}

    filters = SearchFilters(
        freshness=freshness,
        include_domains=include_domains or [],
        exclude_domains=exclude_domains or [],
        category=category,
        include_text=include_text,
        exclude_text=exclude_text,
    )
    filters_dict = {
        "freshness": freshness, "include_domains": include_domains,
        "exclude_domains": exclude_domains, "category": category,
        "include_text": include_text, "exclude_text": exclude_text,
    }

    cache_key = cache.make_cache_key(query, valid_engines, max_results, filters_dict)
    if use_cache:
        cached = await cache.get_search(cache_key, max_age_seconds=max_age_seconds)
        if cached is not None:
            return {"query": query, "engines": valid_engines, "results": cached, "cached": True, "errors": {}}

    results_by_engine: dict[str, list[SearchResult]] = {}
    errors: dict[str, str] = {}

    async def _search_engine(name: str) -> None:
        engine = get_engine(name)
        limiter = get_limiter()
        try:
            await limiter.acquire(name)
            results = await engine.search(query, max_results=settings.max_results_per_engine, filters=filters)
            results_by_engine[name] = results
        except Exception as e:
            errors[name] = str(e)
            logger.warning("引擎 %s 搜索失败: %s", name, e)

    await asyncio.gather(*[_search_engine(n) for n in valid_engines])
    merged = _merge_rrf(results_by_engine, max_results)

    if merged:
        await cache.put_search(cache_key, query, valid_engines, merged)

    return {"query": query, "engines": valid_engines, "results": merged, "cached": False, "errors": errors}


async def _run_research(
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
    """研究工具：搜索 + 抓取。"""
    depth = max(1, min(depth, 8))

    search_result = await _aggregate_search(
        question, engines=engines, max_results=depth, use_cache=use_cache,
        max_age_seconds=max_age_seconds, freshness=freshness,
        include_domains=include_domains, exclude_domains=exclude_domains,
        category=category, include_text=include_text, exclude_text=exclude_text,
    )

    sources = search_result.get("results", [])
    errors = search_result.get("errors", {})
    documents = []
    total_tokens = 0

    if fetch and sources:
        urls = [s["url"] for s in sources[:depth]]
        logger.info("抓取 %d 个页面...", len(urls))
        fetch_results = await fetch_many(urls)
        for i, result in enumerate(fetch_results):
            if isinstance(result, Exception):
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


# ── 辅助函数 ──────────────────────────────────────────────


def _maybe_render(payload: dict[str, Any], fmt: Format, renderer: Any) -> str | dict[str, Any]:
    if fmt == "json":
        return payload
    return renderer(payload)


def _max_age_to_seconds(max_age_hours: float | None) -> int | None:
    if max_age_hours is None:
        return None
    return int(max_age_hours * 3600)


async def _safe_progress(ctx: Context | None, current: float, total: float, message: str) -> None:
    if ctx is None:
        return
    try:
        await ctx.report_progress(current, total, message)
    except (ValueError, AttributeError):
        return


# ── 工具定义 ──────────────────────────────────────────────


@mcp.tool(
    annotations=ToolAnnotations(
        title="Web search (multi-engine, no API key)",
        readOnlyHint=True, idempotentHint=False, openWorldHint=True,
    ),
)
async def search(
    query: str,
    engines: list[str] | None = None,
    max_results: int = 10,
    use_cache: bool = True,
    max_age_hours: float | None = None,
    freshness: Literal["day", "week", "month", "year"] | None = None,
    include_domains: list[str] | None = None,
    exclude_domains: list[str] | None = None,
    category: Literal["news", "pdf", "github", "paper", "forum", "blog"] | None = None,
    include_text: str | None = None,
    exclude_text: str | None = None,
    format: Format = "markdown",
) -> str | dict[str, Any]:
    """Run a multi-engine web search and return a ranked, deduplicated link list.

    Best for:
    - Discovery queries ("what is X", "find me X", "who is X").
    - Getting a list of URLs you can hand to `fetch` next.
    - Topics likely to be after your knowledge cutoff (use `freshness="week"`).

    Not recommended for:
    - You already know the URL -> use `fetch` instead.
    - You want both links AND their full text in one call -> use `research`.

    Returns:
    - markdown (default): numbered list with title, URL, snippet.
    - json: dict with `results`, `engines`, `cached`, optional `errors`, optional `hint`.

    Args:
        query: Natural-language query.
        engines: Subset of `engines()`. None = duckduckgo+bing.
        max_results: Merged result count after dedup.
        use_cache: Reuse the last result within the cache TTL.
        max_age_hours: Treat cached results older than this as a miss.
        freshness: "day"|"week"|"month"|"year".
        include_domains: List of domains to restrict to.
        exclude_domains: List of domains to exclude.
        category: "news"|"pdf"|"github"|"paper"|"forum"|"blog".
        include_text: Substring required in title or snippet.
        exclude_text: Substring forbidden in title or snippet.
        format: "markdown" (default) or "json".
    """
    if not query.strip():
        raise ValueError("query must not be empty")

    payload = await _aggregate_search(
        query, engines=engines, max_results=max_results, use_cache=use_cache,
        max_age_seconds=_max_age_to_seconds(max_age_hours), freshness=freshness,
        include_domains=include_domains, exclude_domains=exclude_domains,
        category=category, include_text=include_text, exclude_text=exclude_text,
    )
    hint = errors_to_hint(payload.get("errors"))
    if hint:
        payload["hint"] = hint
    return _maybe_render(payload, format, render_search)


@mcp.tool(
    annotations=ToolAnnotations(
        title="Fetch URL as Markdown",
        readOnlyHint=True, idempotentHint=True, openWorldHint=True,
    ),
)
async def fetch(
    url: str,
    format: Format = "markdown",
) -> str | dict[str, Any]:
    """Fetch one URL and return reader-mode Markdown of the main content.

    Best for:
    - You already have a URL and need the actual page text.
    - Verifying a single claim by reading the source.

    Not recommended for:
    - Multiple URLs at once -> use `fetch_batch` (not yet implemented).
    - You don't have a URL yet -> use `search` first.

    Returns:
    - markdown (default): metadata header plus the cleaned page body.
    - json: {url, title, content, method, truncated, tokens_estimated}.

    Args:
        url: Absolute http(s) URL.
        format: "markdown" or "json".
    """
    result = await fetch_page(url)
    return _maybe_render(result, format, render_fetch)


@mcp.tool(
    annotations=ToolAnnotations(
        title="List available search engines",
        readOnlyHint=True, idempotentHint=True, openWorldHint=False,
    ),
)
def engines() -> list[str]:
    """List engine names accepted by the `engines=` parameter of `search`.

    Returns:
    - A list of engine name strings.
    """
    return _list_engines()


@mcp.tool(
    annotations=ToolAnnotations(
        title="Search and read in one call",
        readOnlyHint=True, idempotentHint=False, openWorldHint=True,
    ),
)
async def research(
    question: str,
    depth: int = 3,
    engines: list[str] | None = None,
    fetch: bool = True,
    use_cache: bool = True,
    max_age_hours: float | None = None,
    freshness: Literal["day", "week", "month", "year"] | None = None,
    include_domains: list[str] | None = None,
    exclude_domains: list[str] | None = None,
    category: Literal["news", "pdf", "github", "paper", "forum", "blog"] | None = None,
    include_text: str | None = None,
    exclude_text: str | None = None,
    format: Format = "markdown",
    ctx: Context | None = None,
) -> str | dict[str, Any]:
    """One-shot research: search the web, fetch the top results, return both.

    Best for:
    - Open-ended questions that need finding sources AND reading them.
    - Replacing a `search` + N x `fetch` chain with one call.

    Not recommended for:
    - You only need links -> `search` (cheaper, no fetching).
    - You only need to read one URL you already have -> `fetch`.

    Args:
        question: What you want to know, in natural language.
        depth: How many top results to fetch (1-8). 3 is a good default.
        engines: Override the engine set.
        fetch: If False, return source list without reading them.
        use_cache: Reuse cached search/page data within TTL.
        max_age_hours: Treat cached results older than this as a miss.
        freshness: "day"|"week"|"month"|"year".
        include_domains: List of domains to restrict to.
        exclude_domains: List of domains to exclude.
        category: "news"|"pdf"|"github"|"paper"|"forum"|"blog".
        include_text: Substring required in title or snippet.
        exclude_text: Substring forbidden in title or snippet.
        format: "markdown" or "json".
    """
    await _safe_progress(ctx, 0.1, 1.0, "searching engines")

    payload = await _run_research(
        question, depth=depth, engines=engines, fetch=fetch, use_cache=use_cache,
        max_age_seconds=_max_age_to_seconds(max_age_hours),
        page_max_age_seconds=_max_age_to_seconds(max_age_hours),
        freshness=freshness, include_domains=include_domains,
        exclude_domains=exclude_domains, category=category,
        include_text=include_text, exclude_text=exclude_text,
    )

    await _safe_progress(ctx, 1.0, 1.0, "done")
    return _maybe_render(payload, format, render_research)


@mcp.tool(
    annotations=ToolAnnotations(
        title="Extract structured data from a URL",
        readOnlyHint=True,
        idempotentHint=True,
        openWorldHint=True,
    ),
)
async def extract_structured(
    url: str,
    format: Format = "markdown",
) -> str | dict[str, Any]:
    """Pull JSON-LD, OpenGraph, Twitter cards from a web page.

    Best for:
    - Product pages (price, currency, availability, brand, rating).
    - Article pages (author, publish date, image, headline).
    - Cases where `fetch` returns prose but you need fields.

    Not recommended for:
    - Just reading a page -> use `fetch`.
    - Pages that don't publish schema.org metadata.

    Returns:
    - json: {url, json_ld:[], opengraph:{}, twitter_card:{}, microdata:[]}.
    - markdown: a flattened key/value view.

    Args:
        url: Absolute http(s) URL.
        format: "markdown" (default) or "json".
    """
    from .structured import extract_structured as _extract
    from .formatting import render_structured

    payload = await _extract(url)
    return _maybe_render(payload, format, render_structured)


@mcp.tool(
    annotations=ToolAnnotations(
        title="Read a remote document",
        readOnlyHint=True,
        idempotentHint=True,
        openWorldHint=True,
    ),
)
async def read_doc(
    source: str,
    start: int = 0,
    length: int | None = None,
    format: Format = "markdown",
) -> str | dict[str, Any]:
    """Read an http(s) document (PDF) into Markdown.

    Best for:
    - Remote PDFs from an http(s) URL.
    - Paginating through a long document via `start` / `length`.

    Not recommended for:
    - Arbitrary HTML web pages -> `fetch` does reader-mode cleanup.
    - Pages discovered through search -> `fetch` or `research`.

    Returns:
    - markdown (default): rendered document text with a small header.
    - json: {content, title, format, total_chars, start, returned_chars, truncated}.

    Args:
        source: http(s) URL.
        start: Character offset to begin reading from. Default 0.
        length: Max characters to return; None = read to end.
        format: "markdown" or "json".
    """
    from .fetchers.documents import read_pdf
    from .formatting import render_doc

    if start < 0:
        raise ValueError(f"start must be >= 0, got {start}")

    payload = await read_pdf(source, start=start, length=length)
    return _maybe_render(payload, format, render_doc)


# ── 提示词 ────────────────────────────────────────────────


@mcp.prompt(title="Research thoroughly")
def research_prompt(question: str, depth: int = 3) -> str:
    """Instruct the model to do a thorough, cited research pass."""
    from .prompts import research_prompt as _research_prompt
    return _research_prompt(question, depth)


@mcp.prompt(title="Fact-check claim")
def factcheck_prompt(claim: str) -> str:
    """Instruct the model to fact-check a specific claim."""
    from .prompts import factcheck_prompt as _factcheck_prompt
    return _factcheck_prompt(claim)


@mcp.prompt(title="News brief")
def news_brief(topic: str, since: str = "day") -> str:
    """Instruct the model to produce a fresh news brief."""
    from .prompts import news_brief as _news_brief
    return _news_brief(topic, since)


# ── 服务器运行 ────────────────────────────────────────────


def run() -> None:
    """启动 MCP 服务器（stdio 传输）。"""
    try:
        mcp.run()
    finally:
        cache.close()


__all__ = ["mcp", "run"]
