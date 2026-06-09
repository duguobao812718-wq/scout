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
import warnings
from typing import Any

# 抑制 aiohttp 进程退出时的资源清理警告（非功能性问题）
warnings.filterwarnings("ignore", message="Unclosed (client session|connector)", category=ResourceWarning)
logging.getLogger("asyncio").setLevel(logging.CRITICAL)

import aiohttp
from bs4 import BeautifulSoup

from ..config import settings

logger = logging.getLogger("scout.fetcher")

# 需要浏览器指纹的引擎（绕过反爬检测）
_BROWSER_ENGINES = {"duckduckgo", "brave", "google", "startpage", "ddg_news"}

# 共享 aiohttp session（复用连接池）
_session: aiohttp.ClientSession | None = None
_session_lock = asyncio.Lock()


async def _get_session() -> aiohttp.ClientSession:
    """获取共享的 aiohttp session（懒初始化，复用连接池，线程安全）。"""
    global _session
    async with _session_lock:
        if _session is None or _session.closed:
            timeout = aiohttp.ClientTimeout(total=settings.request_timeout)
            headers = {
                "User-Agent": settings.user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": settings.accept_language,
            }
            _session = aiohttp.ClientSession(headers=headers, timeout=timeout)
        return _session


async def close_session() -> None:
    """关闭共享 session（应用关闭时调用）。"""
    global _session
    if _session and not _session.closed:
        await _session.close()
        _session = None


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
    # SSRF 防护（引擎搜索 URL 跳过检查，因为搜索引擎 URL 是可信的）
    if engine is None:
        from ..url_safety import assert_url_allowed
        await assert_url_allowed(url)

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
    headers: dict[str, str] | None = None,
) -> str:
    """使用 aiohttp 抓取（复用共享 session，手动处理重定向防 SSRF 绕过）。"""
    from ..url_safety import assert_url_allowed

    session = await _get_session()
    current_url = url
    for _ in range(10):  # 最多 10 次重定向
        async with session.get(
            current_url, proxy=proxy,
            timeout=aiohttp.ClientTimeout(total=timeout),
            allow_redirects=False,
            headers=headers,
        ) as response:
            if response.status in (301, 302, 303, 307, 308):
                location = response.headers.get("Location")
                if not location:
                    response.raise_for_status()
                    break
                from urllib.parse import urljoin
                current_url = urljoin(current_url, location)
                await assert_url_allowed(current_url)
                continue
            response.raise_for_status()
            html = await response.text()
            break
    else:
        raise ValueError(f"重定向次数过多: {url}")

    if not html or not html.strip():
        raise ValueError(f"响应为空: {url}")

    return html


async def _fetch_with_curl_cffi(
    url: str,
    timeout: float,
    proxy: str | None,
) -> str:
    """使用 curl_cffi 抓取（浏览器指纹模拟，手动处理重定向防 SSRF 绕过）。"""

    from ..url_safety import assert_url_allowed

    # 获取共享的 curl_cffi session
    session = await _get_curl_cffi_session()
    current_url = url
    for _ in range(10):  # 最多 10 次重定向
        response = await session.get(
            current_url,
            timeout=timeout,
            proxies={"https": proxy, "http": proxy} if proxy else None,
            allow_redirects=False,
        )
        if response.status_code in (301, 302, 303, 307, 308):
            location = response.headers.get("Location")
            if not location:
                response.raise_for_status()
                break
            from urllib.parse import urljoin
            current_url = urljoin(current_url, location)
            await assert_url_allowed(current_url)
            continue
        response.raise_for_status()
        html = response.text
        break
    else:
        raise ValueError(f"重定向次数过多: {url}")

    if not html or not html.strip():
        raise ValueError(f"响应为空: {url}")

    return html


# 共享 curl_cffi session（复用连接池）
_curl_cffi_session: Any | None = None
_curl_cffi_session_lock = asyncio.Lock()


async def _get_curl_cffi_session() -> Any:
    """获取共享的 curl_cffi session（懒初始化，复用连接池，线程安全）。"""
    global _curl_cffi_session
    async with _curl_cffi_session_lock:
        if _curl_cffi_session is None:
            from curl_cffi.requests import AsyncSession
            _curl_cffi_session = AsyncSession(impersonate="chrome")
        return _curl_cffi_session


async def close_curl_cffi_session() -> None:
    """关闭共享 curl_cffi session（应用关闭时调用）。"""
    global _curl_cffi_session
    if _curl_cffi_session is not None:
        await _curl_cffi_session.close()
        _curl_cffi_session = None


async def fetch_page(
    url: str,
    timeout: float | None = None,
    proxy: str | None = None,
    engine: str | None = None,
    use_cache: bool = True,
) -> dict[str, Any]:
    """抓取 URL 并提取主要内容。

    支持缓存读写：如果页面已在缓存中且 use_cache=True，直接返回缓存内容。
    """
    from ..cache import cache
    from ..formatting import estimate_tokens, smart_truncate
    from ..url_safety import assert_url_allowed

    # SSRF 防护（用户直接调用 fetch 时检查）
    if engine is None:
        await assert_url_allowed(url)

    # 尝试从缓存读取
    if use_cache:
        cached = await cache.get_page(url)
        if cached:
            logger.debug("缓存命中: %s", url)
            return cached

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

    result = {
        "url": url,
        "title": title,
        "content": content,
        "method": "http",
        "truncated": truncated,
        "tokens_estimated": estimate_tokens(content),
    }

    # 写入缓存
    if use_cache:
        try:
            await cache.put_page(url, title, content, engine or "fetch")
            logger.debug("页面已缓存: %s", url)
        except Exception as e:
            logger.debug("缓存写入失败 %s: %s", url, e)

    return result


# 并发抓取的信号量限制
_fetch_semaphore = asyncio.Semaphore(5)


async def fetch_many(
    urls: list[str],
    timeout: float | None = None,
    proxy: str | None = None,
    engine: str | None = None,
    use_cache: bool = True,
) -> list[dict[str, Any] | Exception]:
    """并发抓取多个 URL（最多 5 个并发）。"""

    async def _fetch_one(url: str) -> dict[str, Any] | Exception:
        async with _fetch_semaphore:
            try:
                return await fetch_page(url, timeout=timeout, proxy=proxy, engine=engine, use_cache=use_cache)
            except Exception as e:
                logger.warning("抓取失败 %s: %s", url, e)
                return e

    tasks = [_fetch_one(url) for url in urls]
    return await asyncio.gather(*tasks)
