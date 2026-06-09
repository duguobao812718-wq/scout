"""
Scout MCP 服务器入口。

使用 FastMCP 框架，注册搜索工具供 AI Agent 调用。
包含 8 个工具 + 4 个提示词。
"""

import asyncio
import logging
from typing import Any, Literal
from urllib.parse import urlparse

from mcp.server.fastmcp import Context, FastMCP
from mcp.types import ToolAnnotations

from .cache import cache
from .config import settings
from .engines import SearchFilters, SearchResult, get_engine
from .engines import list_engines as _list_engines
from .fetchers.http import fetch_many, fetch_page
from .formatting import (
    errors_to_hint,
    render_fetch,
    render_research,
    render_search,
)
from .ratelimit import get_limiter
from .scoring import compute_quality_bonus
from .utils import normalize_url, title_similarity  # noqa: F401 (used in _merge_rrf)

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
    """Reciprocal Rank Fusion 合并 + URL 归一化去重。"""
    # 用归一化 URL 做 key，保留原始 URL
    norm_to_canonical: dict[str, str] = {}  # normalized -> original URL
    url_scores: dict[str, float] = {}
    url_info: dict[str, dict[str, Any]] = {}

    for engine_name, results in results_by_engine.items():
        for rank, result in enumerate(results, 1):
            normalized = normalize_url(result.url)

            # 找到已有的 canonical URL（如果此 URL 的变体已出现过）
            canonical = norm_to_canonical.get(normalized)
            if canonical is None:
                # 新 URL，建立映射
                canonical = result.url
                norm_to_canonical[normalized] = canonical

            score = 1.0 / (_RRF_K + rank)
            url_scores[canonical] = url_scores.get(canonical, 0) + score

            if canonical not in url_info:
                url_info[canonical] = {
                    "title": result.title,
                    "url": result.url,
                    "snippet": result.snippet,
                    "engines": [],
                    "published_age": result.published_age,
                }
            url_info[canonical]["engines"].append(engine_name)
            # 保留最长的摘要
            if len(result.snippet) > len(url_info[canonical]["snippet"]):
                url_info[canonical]["snippet"] = result.snippet
            # 保留更详细的标题（如果当前标题更长）
            if len(result.title) > len(url_info[canonical]["title"]):
                url_info[canonical]["title"] = result.title

    # 应用质量加分
    final_scores: dict[str, float] = {}
    for url, rrf_score in url_scores.items():
        info = url_info[url]
        quality_bonus = compute_quality_bonus(
            url=url,
            title=info["title"],
            snippet=info["snippet"],
            engine_count=len(info["engines"]),
            published_age=info.get("published_age", ""),
        )
        final_scores[url] = rrf_score + quality_bonus

    sorted_urls = sorted(final_scores.keys(), key=lambda u: final_scores[u], reverse=True)

    # 跨域名标题去重
    seen_hosts: dict[str, list[str]] = {}  # host -> [title1, title2, ...]
    merged = []
    for url in sorted_urls:
        info = url_info[url]
        host = urlparse(url).hostname or ""
        title = info["title"]

        if host in seen_hosts:
            # 检查同域名下是否有高度相似的标题
            duplicate = False
            for seen_title in seen_hosts[host]:
                if title_similarity(title, seen_title) > 0.8:
                    duplicate = True
                    break
            if duplicate:
                continue
            seen_hosts[host].append(title.lower())
        else:
            seen_hosts[host] = [title.lower()]

        merged.append({
            "title": info["title"],
            "url": info["url"],
            "snippet": info["snippet"],
            "engines": info["engines"],
            "score": final_scores[url],
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
        cached, is_stale = await cache.get_search(cache_key, max_age_seconds=max_age_seconds)
        if cached is not None:
            # stale-while-revalidate：先返回旧缓存，后台刷新
            if is_stale:
                logger.info("缓存 stale 命中，后台刷新: %s", query[:50])
                # 不等待后台任务完成，直接返回旧数据
                task = asyncio.create_task(_refresh_search_cache(
                    cache_key, query, valid_engines, filters, max_results,
                ))
                task.add_done_callback(lambda t: t.exception() if not t.cancelled() else None)
            return {
                "query": query, "engines": valid_engines, "results": cached,
                "cached": True, "stale": is_stale, "errors": {},
            }

    results_by_engine: dict[str, list[SearchResult]] = {}
    errors: dict[str, Any] = {}
    diagnostics: dict[str, Any] = {}

    async def _search_engine(name: str) -> None:
        engine = get_engine(name)
        limiter = get_limiter()
        try:
            await limiter.acquire(name)
            results = await engine.search(
                query, max_results=settings.max_results_per_engine,
                filters=filters, diagnostics=diagnostics,
            )
            results_by_engine[name] = results
            # 记录成功
            limiter.record_success(name)
            # 从 diagnostics 提取结构化错误信息
            engine_diag = diagnostics.get(name, {})
            if engine_diag.get("error"):
                errors[name] = {
                    "error": engine_diag["error"],
                    "error_kind": engine_diag.get("error_kind", "transient"),
                }
        except Exception as e:
            # 记录失败
            limiter.record_failure(name)
            errors[name] = {"error": str(e), "error_kind": "transient"}
            logger.warning("引擎 %s 搜索失败: %s", name, e)

    await asyncio.gather(*[_search_engine(n) for n in valid_engines])
    merged = _merge_rrf(results_by_engine, max_results)

    if merged:
        await cache.put_search(cache_key, query, valid_engines, merged)

    # 收集搜索建议
    all_related: list[str] = []
    spell_correction: str | None = None
    for name in valid_engines:
        engine_diag = diagnostics.get(name, {})
        related = engine_diag.get("related_searches", [])
        all_related.extend(related)
        if not spell_correction and engine_diag.get("spell_correction"):
            spell_correction = engine_diag["spell_correction"]

    # 去重相关搜索
    seen = set()
    unique_related = []
    for term in all_related:
        if term.lower() not in seen:
            seen.add(term.lower())
            unique_related.append(term)

    # 查询改写建议
    from .suggestions import rewrite_query
    rewrites = rewrite_query(query)

    payload = {"query": query, "engines": valid_engines, "results": merged, "cached": False, "errors": errors}

    # 附加建议（如果有）
    if unique_related:
        payload["related_searches"] = unique_related[:10]
    if spell_correction:
        payload["spell_correction"] = spell_correction
    if rewrites:
        payload["query_suggestions"] = rewrites

    return payload


async def _refresh_search_cache(
    cache_key: str,
    query: str,
    engines: list[str],
    filters: SearchFilters,
    max_results: int,
) -> None:
    """后台刷新搜索缓存（stale-while-revalidate）。"""
    try:
        results_by_engine: dict[str, list[SearchResult]] = {}

        async def _refresh_engine(name: str) -> None:
            engine = get_engine(name)
            limiter = get_limiter()
            try:
                await limiter.acquire(name)
                results = await engine.search(query, max_results=settings.max_results_per_engine, filters=filters)
                results_by_engine[name] = results
            except Exception as e:
                logger.debug("后台刷新引擎 %s 失败: %s", name, e)

        await asyncio.gather(*[_refresh_engine(n) for n in engines])
        merged = _merge_rrf(results_by_engine, max_results)
        if merged:
            await cache.put_search(cache_key, query, engines, merged)
            logger.debug("后台缓存刷新完成: %s", query[:50])
    except Exception as e:
        logger.warning("后台缓存刷新失败: %s", e)


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
    - Multiple URLs at once -> use `fetch_batch`.
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
        title="Fetch multiple URLs",
        readOnlyHint=True, idempotentHint=True, openWorldHint=True,
    ),
)
async def fetch_batch(
    urls: list[str],
    format: Format = "markdown",
) -> str | dict[str, Any]:
    """Fetch multiple URLs in parallel and return their contents.

    Best for:
    - You have a list of URLs from `search` and want to read them all.
    - Bulk data collection from known sources.

    Not recommended for:
    - You only need one URL -> use `fetch`.
    - You don't have URLs yet -> use `search` first.

    Returns:
    - json: {results: [{url, title, content, ...}], errors: {index: msg}}.
    - markdown: concatenated results with headers.

    Args:
        urls: List of absolute http(s) URLs (max 10).
        format: "markdown" or "json".
    """
    if not urls:
        raise ValueError("urls must not be empty")
    urls = urls[:10]

    results = await fetch_many(urls)

    documents = []
    errors: dict[str, str] = {}
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            errors[f"fetch_{i}"] = f"{urls[i]}: {result}"
        else:
            documents.append(result)

    payload = {"urls": urls, "documents": documents, "errors": errors}

    if format == "json":
        return payload

    # markdown 渲染（包含成功和失败结果）
    lines = []
    for doc in documents:
        lines.append(f"# {doc.get('title', '(无标题)')}")
        lines.append(f"URL: {doc['url']}")
        lines.append("")
        lines.append(doc.get("content", ""))
        lines.append("\n---\n")

    if errors:
        lines.append("# 抓取失败")
        for _key, msg in errors.items():
            lines.append(f"- {msg}")
        lines.append("")

    return "\n".join(lines)


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
        title="Search cached pages",
        readOnlyHint=True, idempotentHint=True, openWorldHint=False,
    ),
)
async def cache_search(
    query: str,
    limit: int = 10,
    format: Format = "markdown",
) -> str | dict[str, Any]:
    """Full-text search across previously fetched and cached pages.

    Best for:
    - Finding content from pages you've already fetched via `fetch` or `research`.
    - Searching your local knowledge base of cached web content.

    Not recommended for:
    - First-time search -> use `search` or `research`.
    - Pages not yet fetched -> use `fetch` first.

    Returns:
    - markdown (default): list of matching pages with snippets.
    - json: {query, results: [{url, title, snippet}]}.

    Args:
        query: Search query (supports FTS5 syntax).
        limit: Max results to return.
        format: "markdown" or "json".
    """
    if not query.strip():
        raise ValueError("query must not be empty")

    results = await cache.search_pages(query, limit=limit)
    payload = {"query": query, "results": results, "count": len(results)}

    if format == "json":
        return payload

    if not results:
        return "_缓存中未找到匹配内容。_\n"

    lines = []
    for i, r in enumerate(results, 1):
        title = r.get("title", "(无标题)")
        url = r.get("url", "")
        snippet = r.get("snippet", "")
        lines.append(f"{i}. **{title}**")
        lines.append(f"   <{url}>")
        if snippet:
            lines.append(f"   {snippet}")
    return "\n".join(lines)


@mcp.tool(
    annotations=ToolAnnotations(
        title="Semantic search indexed pages",
        readOnlyHint=True, idempotentHint=True, openWorldHint=False,
    ),
)
async def semantic_search(
    query: str,
    top_k: int = 10,
    format: Format = "markdown",
) -> str | dict[str, Any]:
    """Search through semantically indexed pages using meaning-based matching.

    Best for:
    - Finding pages by concept rather than exact keywords.
    - "Find me pages about X" when keyword search misses.
    - Searching content you've already indexed via `semantic_index`.

    Not recommended for:
    - First-time search -> use `search` or `research`.
    - You haven't indexed any content yet -> use `semantic_index` first.

    Requires: pip install scout[semantic]

    Returns:
    - markdown (default): ranked list with similarity scores.
    - json: {query, results: [{url, title, content, score}]}.

    Args:
        query: Natural-language description of what you're looking for.
        top_k: Max results to return.
        format: "markdown" or "json".
    """
    if not query.strip():
        raise ValueError("query must not be empty")

    try:
        from .semantic import semantic_index
    except ImportError:
        return _maybe_render(
            {"error": "语义搜索需要额外安装: pip install scout[semantic]"},
            format, lambda p: f"_{p['error']}_\n",
        )

    results = await semantic_index.search(query, top_k=top_k)
    payload = {"query": query, "results": results, "count": len(results)}

    if format == "json":
        return payload

    if not results:
        return "_未找到语义匹配的内容。请先用 `semantic_index` 索引页面。_\n"

    lines = []
    for i, r in enumerate(results, 1):
        title = r.get("title", "(无标题)")
        url = r.get("url", "")
        score = r.get("score", 0)
        content = r.get("content", "")[:200]
        lines.append(f"{i}. **{title}** (相似度: {score:.3f})")
        lines.append(f"   <{url}>")
        if content:
            lines.append(f"   {content}")
    return "\n".join(lines)


@mcp.tool(
    annotations=ToolAnnotations(
        title="Index a page for semantic search",
        readOnlyHint=False, idempotentHint=True, openWorldHint=True,
    ),
)
async def semantic_index_page(
    url: str,
    format: Format = "markdown",
) -> str | dict[str, Any]:
    """Fetch a page and add it to the semantic search index.

    Best for:
    - Indexing important pages for later semantic retrieval.
    - Building a knowledge base that `semantic_search` can query.

    Not recommended for:
    - Just reading a page -> use `fetch`.
    - You don't need semantic search -> use `cache_search` instead.

    Requires: pip install scout[semantic]

    Returns:
    - markdown (default): confirmation with page title.
    - json: {url, title, indexed: true}.

    Args:
        url: Absolute http(s) URL to fetch and index.
        format: "markdown" or "json".
    """
    try:
        from .semantic import semantic_index
    except ImportError:
        msg = "语义搜索需要额外安装: pip install scout[semantic]"
        return _maybe_render({"error": msg}, format, lambda p: f"_{p['error']}_\n")

    # 抓取页面
    page = await fetch_page(url)

    # 添加到索引
    await semantic_index.add(
        url=page["url"],
        title=page.get("title", ""),
        content=page.get("content", ""),
    )

    payload = {
        "url": page["url"],
        "title": page.get("title", ""),
        "indexed": True,
        "truncated": page.get("truncated", False),
    }

    if format == "json":
        return payload

    return f"✅ 已索引: **{page.get('title', url)}**\n\n可用 `semantic_search` 搜索此内容。"


@mcp.tool(
    annotations=ToolAnnotations(
        title="Image search via SearXNG",
        readOnlyHint=True, idempotentHint=False, openWorldHint=True,
    ),
)
async def image_search(
    query: str,
    max_results: int = 10,
    freshness: Literal["day", "week", "month", "year"] | None = None,
    format: Format = "markdown",
) -> str | dict[str, Any]:
    """Search for images using SearXNG meta-search engine.

    Best for:
    - Finding images related to a topic.
    - Getting image URLs for visual content.

    Returns:
    - markdown (default): list with image URLs and source pages.
    - json: {query, results: [{title, url, image_url, width, height}]}.

    Args:
        query: Image search query.
        max_results: Max results to return.
        freshness: "day"|"week"|"month"|"year".
        format: "markdown" or "json".
    """
    if not query.strip():
        raise ValueError("query must not be empty")

    filters = SearchFilters(freshness=freshness)

    try:
        from .engines.searxng import SearxNGEngine
        engine = SearxNGEngine()
        results = await engine.search_images(query, max_results=max_results, filters=filters)
    except Exception as e:
        results = []
        logger.warning("图片搜索失败: %s", e)

    payload = {"query": query, "results": results, "count": len(results)}

    if format == "json":
        return payload

    if not results:
        return "_未找到图片结果。_\n"

    lines = []
    for i, r in enumerate(results, 1):
        title = r.get("title", "(无标题)")
        page_url = r.get("url", "")
        img_url = r.get("image_url", "")
        lines.append(f"{i}. **{title}**")
        if img_url:
            lines.append(f"   图片: <{img_url}>")
        if page_url:
            lines.append(f"   来源: <{page_url}>")
    return "\n".join(lines)


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
        title="Summarize with credibility assessment",
        readOnlyHint=True, idempotentHint=False, openWorldHint=True,
    ),
)
async def summarize(
    question: str,
    depth: int = 5,
    engines: list[str] | None = None,
    freshness: Literal["day", "week", "month", "year"] | None = None,
    include_domains: list[str] | None = None,
    exclude_domains: list[str] | None = None,
    format: Format = "markdown",
) -> str | dict[str, Any]:
    """Search, fetch, extract key points, and assess credibility.

    Best for:
    - Questions needing trustworthy, multi-source answers.
    - When you need a credibility score for the sources.
    - Replacing research + manual summarization.

    Not recommended for:
    - You only need links -> use search.
    - You only need one page -> use fetch.

    Returns:
    - markdown (default): structured summary with key points and credibility.
    - json: {question, sources, key_points, credibility}.

    Args:
        question: What you want to know.
        depth: How many sources to fetch (1-8). 5 is a good default.
        engines: Override the engine set.
        freshness: "day"|"week"|"month"|"year".
        include_domains: Restrict to these domains.
        exclude_domains: Exclude these domains.
        format: "markdown" or "json".
    """
    from .summary import compute_credibility, extract_key_points, format_summary_for_agent

    depth = max(1, min(depth, 8))

    # 搜索
    search_result = await _aggregate_search(
        question, engines=engines, max_results=depth,
        freshness=freshness, include_domains=include_domains,
        exclude_domains=exclude_domains,
    )

    sources = search_result.get("results", [])

    # 抓取页面
    documents = []
    if sources:
        urls = [s["url"] for s in sources[:depth]]
        fetch_results = await fetch_many(urls)
        for result in fetch_results:
            if not isinstance(result, Exception):
                documents.append(result)

    # 提取关键要点
    all_key_points: dict[str, list[str]] = {}
    for doc in documents:
        title = doc.get("title", doc.get("url", ""))
        points = extract_key_points(doc.get("content", ""))
        if points:
            all_key_points[title] = points

    # 可信度评估
    credibility = compute_credibility(sources)

    if format == "json":
        return {
            "question": question,
            "sources": sources,
            "key_points": all_key_points,
            "credibility": credibility,
            "errors": search_result.get("errors", {}),
        }

    return format_summary_for_agent(question, sources, documents)


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
    from .formatting import render_structured
    from .structured import extract_structured as _extract

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


# ── MCP 资源 ────────────────────────────────────────────────


@mcp.resource(
    "cache://stats",
    name="cache_stats",
    title="Cache statistics",
    description="Current cache entry counts and configuration.",
    mime_type="application/json",
)
async def resource_cache_stats() -> dict[str, Any]:
    """返回缓存统计信息。"""
    stats = await cache.stats()
    from .config import settings
    return {
        **stats,
        "cache_ttl_seconds": settings.cache_ttl_seconds,
        "cache_dir": str(settings.cache_dir),
    }


@mcp.resource(
    "cache://page/{url}",
    name="cached_page",
    title="Cached page content",
    description="Read a previously fetched page from the local cache.",
    mime_type="text/markdown",
)
async def resource_cached_page(url: str) -> str:
    """从缓存读取已抓取的页面内容。"""

    page, is_stale = await cache.get_page(url)
    if page is None:
        return f"_页面未缓存: {url}_\n\n请先使用 `fetch` 工具抓取此页面。"

    title = page.get("title", "(无标题)")
    content = page.get("content", "")
    stale_mark = " ⚠️ 已过期" if is_stale else ""

    return f"# {title}{stale_mark}\n\n> URL: <{url}>\n\n{content}"


@mcp.resource(
    "engines://list",
    name="engines_list",
    title="Available search engines",
    description="List of all registered search engines with their capabilities.",
    mime_type="application/json",
)
async def resource_engines_list() -> list[dict[str, Any]]:
    """返回所有可用引擎及其能力。"""
    from .engines import ENGINES

    return [
        {
            "name": engine.name,
            "needs_browser": engine.needs_browser,
            "supports_freshness": engine.supports_freshness,
            "supports_safesearch": engine.supports_safesearch,
        }
        for engine in ENGINES.values()
    ]


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


@mcp.prompt(title="Compare sources")
def compare_sources(question: str, sources: str) -> str:
    """Instruct the model to compare and cross-reference multiple sources."""
    from .prompts import compare_sources as _compare_sources
    return _compare_sources(question, sources)


# ── 服务器运行 ────────────────────────────────────────────


def run() -> None:
    """启动 MCP 服务器（stdio 传输）。"""
    import atexit

    def _cleanup():
        """清理资源。"""
        cache.close()
        # 关闭共享 aiohttp session
        try:
            from .fetchers.http import _session, close_session
            if _session is not None and not _session.closed:
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = None
                if loop and loop.is_running():
                    asyncio.ensure_future(close_session())
                else:
                    new_loop = asyncio.new_event_loop()
                    new_loop.run_until_complete(close_session())
                    new_loop.close()
        except Exception:
            pass

    atexit.register(_cleanup)

    try:
        mcp.run()
    finally:
        _cleanup()


__all__ = ["mcp", "run"]
