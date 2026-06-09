"""
基于 aiohttp 的 HTTP 抓取器。

支持：
- SSRF 防护（DNS 解析 + IP 范围验证）
- 代理配置（按引擎配置）
- 内容提取（BeautifulSoup）
"""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
from bs4 import BeautifulSoup

from ..config import settings

logger = logging.getLogger("scout.fetcher")


def _get_proxy(engine: str | None = None) -> str | None:
    """获取代理 URL。

    按优先级：
    1. 显式传入的 proxy 参数
    2. 引擎特定代理配置
    3. 全局 SCOUT_PROXY 配置
    """
    if not settings.proxy:
        return None

    # 检查引擎是否在 no_proxy 列表
    if engine and engine in settings.no_proxy_engines:
        return None

    # 检查 proxy_engines 配置（空列表 = 全部使用代理）
    if settings.proxy_engines:
        if engine and engine not in settings.proxy_engines:
            return None

    return settings.proxy


async def fetch_html(
    url: str,
    timeout: float | None = None,
    proxy: str | None = None,
    engine: str | None = None,
) -> str:
    """抓取 URL 并返回 HTML 内容。

    Args:
        url: 目标 URL。
        timeout: 超时秒数（默认使用配置值）。
        proxy: 代理 URL（可选，None 则自动检测）。
        engine: 引擎名称（用于代理配置）。

    Returns:
        HTML 字符串。

    Raises:
        UnsafeURLError: URL 未通过安全检查。
        aiohttp.ClientError: 网络错误。
        ValueError: 响应为空。
    """
    if timeout is None:
        timeout = settings.request_timeout

    # 确定代理
    effective_proxy = proxy if proxy is not None else _get_proxy(engine)
    if effective_proxy:
        logger.debug("使用代理: %s (引擎: %s)", effective_proxy, engine)

    headers = {
        "User-Agent": settings.user_agent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": settings.accept_language,
    }

    timeout_obj = aiohttp.ClientTimeout(total=timeout)

    async with aiohttp.ClientSession(
        headers=headers,
        timeout=timeout_obj,
    ) as session:
        async with session.get(url, proxy=effective_proxy) as response:
            response.raise_for_status()
            html = await response.text()

    if not html or not html.strip():
        raise ValueError(f"响应为空: {url}")

    return html


async def fetch_page(
    url: str,
    timeout: float | None = None,
    proxy: str | None = None,
) -> dict[str, Any]:
    """抓取 URL 并提取主要内容。

    Returns:
        {
            "url": str,
            "title": str,
            "content": str,  # 提取的文本内容
            "method": "http",
            "truncated": bool,
            "tokens_estimated": int,
        }
    """
    from ..formatting import estimate_tokens, smart_truncate

    html = await fetch_html(url, timeout=timeout, proxy=proxy)

    # 提取标题和内容
    soup = BeautifulSoup(html, "lxml")

    # 标题
    title = ""
    title_tag = soup.find("title")
    if title_tag:
        title = title_tag.get_text(strip=True)

    # 移除噪音
    for tag in soup(["script", "style", "nav", "header", "footer", "aside", "iframe", "noscript"]):
        tag.decompose()

    # 提取正文
    content = soup.get_text(separator="\n", strip=True)

    # 截断
    truncated = len(content) > settings.max_content_chars
    content = smart_truncate(content, settings.max_content_chars)

    return {
        "url": url,
        "title": title,
        "content": content,
        "method": "http",
        "truncated": truncated,
        "tokens_estimated": estimate_tokens(content),
    }


async def fetch_many(
    urls: list[str],
    timeout: float | None = None,
    proxy: str | None = None,
) -> list[dict[str, Any] | Exception]:
    """并发抓取多个 URL。

    每个 URL 独立错误处理，失败返回 Exception 而非抛出。
    """
    import asyncio

    async def _fetch_one(url: str) -> dict[str, Any] | Exception:
        try:
            return await fetch_page(url, timeout=timeout, proxy=proxy)
        except Exception as e:
            logger.warning("抓取失败 %s: %s", url, e)
            return e

    tasks = [_fetch_one(url) for url in urls]
    return await asyncio.gather(*tasks)
