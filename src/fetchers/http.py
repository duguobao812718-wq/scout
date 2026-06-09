"""
HTTP 抓取器。

支持：
- curl_cffi 浏览器指纹模拟（绕过 DuckDuckGo CAPTCHA）
- aiohttp 标准请求
- 代理配置（按引擎配置）
- 内容提取（BeautifulSoup）
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp
from bs4 import BeautifulSoup

from ..config import settings

logger = logging.getLogger("scout.fetcher")

# 需要浏览器指纹的引擎
_BROWSER_ENGINES = {"duckduckgo"}


def _get_proxy(engine: str | None = None) -> str | None:
    """获取代理 URL。"""
    if not settings.proxy:
        return None
    if engine and engine in settings.no_proxy_engines:
        return None
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

    对于需要浏览器指纹的引擎（如 DuckDuckGo），使用 curl_cffi。
    其他引擎使用 aiohttp。
    """
    if timeout is None:
        timeout = settings.request_timeout

    effective_proxy = proxy if proxy is not None else _get_proxy(engine)

    # 判断是否需要浏览器指纹
    if engine in _BROWSER_ENGINES:
        return await _fetch_with_curl_cffi(url, timeout, effective_proxy)
    else:
        return await _fetch_with_aiohttp(url, timeout, effective_proxy)


async def _fetch_with_aiohttp(
    url: str,
    timeout: float,
    proxy: str | None,
) -> str:
    """使用 aiohttp 抓取。"""
    headers = {
        "User-Agent": settings.user_agent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": settings.accept_language,
    }

    timeout_obj = aiohttp.ClientTimeout(total=timeout)

    async with aiohttp.ClientSession(headers=headers, timeout=timeout_obj) as session:
        async with session.get(url, proxy=proxy) as response:
            response.raise_for_status()
            html = await response.text()

    if not html or not html.strip():
        raise ValueError(f"响应为空: {url}")

    return html


async def _fetch_with_curl_cffi(
    url: str,
    timeout: float,
    proxy: str | None,
) -> str:
    """使用 curl_cffi 抓取（浏览器指纹模拟）。"""
    from curl_cffi.requests import AsyncSession

    async with AsyncSession(impersonate="chrome") as session:
        response = await session.get(
            url,
            timeout=timeout,
            proxies={"https": proxy, "http": proxy} if proxy else None,
        )
        response.raise_for_status()
        html = response.text

    if not html or not html.strip():
        raise ValueError(f"响应为空: {url}")

    return html


async def fetch_page(
    url: str,
    timeout: float | None = None,
    proxy: str | None = None,
    engine: str | None = None,
) -> dict[str, Any]:
    """抓取 URL 并提取主要内容。"""
    from ..formatting import estimate_tokens, smart_truncate

    html = await fetch_html(url, timeout=timeout, proxy=proxy, engine=engine)

    soup = BeautifulSoup(html, "lxml")

    title = ""
    title_tag = soup.find("title")
    if title_tag:
        title = title_tag.get_text(strip=True)

    for tag in soup(["script", "style", "nav", "header", "footer", "aside", "iframe", "noscript"]):
        tag.decompose()

    content = soup.get_text(separator="\n", strip=True)
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
    engine: str | None = None,
) -> list[dict[str, Any] | Exception]:
    """并发抓取多个 URL。"""

    async def _fetch_one(url: str) -> dict[str, Any] | Exception:
        try:
            return await fetch_page(url, timeout=timeout, proxy=proxy, engine=engine)
        except Exception as e:
            logger.warning("抓取失败 %s: %s", url, e)
            return e

    tasks = [_fetch_one(url) for url in urls]
    return await asyncio.gather(*tasks)
