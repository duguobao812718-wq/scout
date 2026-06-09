"""
文档抓取模块。

支持 PDF、DOCX 等文档格式的内容提取。
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger("scout.documents")


async def read_pdf(
    url: str,
    start: int = 0,
    length: int | None = None,
    max_pages: int = 100,
) -> dict[str, Any]:
    """读取远程 PDF 文档。

    Args:
        url: PDF 文档 URL。
        start: 起始字符位置。
        length: 返回的最大字符数。
        max_pages: 最大页数。

    Returns:
        {
            "url": str,
            "title": str,
            "content": str,
            "format": "pdf",
            "total_chars": int,
            "start": int,
            "returned_chars": int,
            "truncated": bool,
        }
    """
    from ..config import settings
    from ..url_safety import assert_url_allowed

    # SSRF 防护
    await assert_url_allowed(url)

    # 下载 PDF
    logger.info("下载 PDF: %s", url)

    # 使用 aiohttp 下载（带超时和大小限制，流式读取防止内存耗尽）
    import aiohttp

    timeout = aiohttp.ClientTimeout(total=settings.request_timeout)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url, proxy=settings.proxy, allow_redirects=False) as response:
            # 手动处理重定向，每次重定向都验证目标 IP
            redirect_count = 0
            while response.status in (301, 302, 303, 307, 308) and redirect_count < 10:
                location = response.headers.get("Location")
                if not location:
                    break
                # 处理相对 URL
                from urllib.parse import urljoin
                location = urljoin(url, location)
                from ..url_safety import assert_url_allowed
                await assert_url_allowed(location)
                redirect_count += 1
                response = await session.get(location, proxy=settings.proxy, allow_redirects=False)

            response.raise_for_status()
            # 流式读取，累积超过限制立即中断
            content_length = response.headers.get("Content-Length")
            if content_length and int(content_length) > settings.max_response_bytes:
                raise ValueError(f"PDF 文件过大: {content_length} bytes (限制: {settings.max_response_bytes})")
            chunks: list[bytes] = []
            total_size = 0
            async for chunk in response.content.iter_chunked(65536):
                total_size += len(chunk)
                if total_size > settings.max_response_bytes:
                    raise ValueError(f"PDF 文件过大 (限制: {settings.max_response_bytes})")
                chunks.append(chunk)
            pdf_bytes = b"".join(chunks)

    # 解析 PDF
    content = await asyncio.to_thread(
        _extract_pdf_content,
        pdf_bytes,
        max_pages,
    )

    # 分页
    total_chars = len(content)
    if start < 0:
        start = 0
    if start >= total_chars:
        return {
            "url": url,
            "title": "",
            "content": "",
            "format": "pdf",
            "total_chars": total_chars,
            "start": start,
            "returned_chars": 0,
            "truncated": False,
        }

    end = len(content)
    if length is not None:
        end = min(start + length, total_chars)

    extracted = content[start:end]
    truncated = end < total_chars

    # 提取标题（从元数据或文件名）
    title = _extract_pdf_title(pdf_bytes) or url.split("/")[-1]

    return {
        "url": url,
        "title": title,
        "content": extracted,
        "format": "pdf",
        "total_chars": total_chars,
        "start": start,
        "returned_chars": len(extracted),
        "truncated": truncated,
    }


def _extract_pdf_content(pdf_bytes: bytes, max_pages: int = 100) -> str:
    """从 PDF 字节中提取文本内容。"""
    import pdfplumber
    import io

    content_parts = []

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for i, page in enumerate(pdf.pages[:max_pages]):
            try:
                text = page.extract_text()
                if text:
                    content_parts.append(text)
            except Exception as e:
                logger.warning("PDF 页面 %d 提取失败: %s", i + 1, e)
                continue

    return "\n\n".join(content_parts)


def _extract_pdf_title(pdf_bytes: bytes) -> str:
    """从 PDF 元数据中提取标题。"""
    import pdfplumber
    import io

    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            metadata = pdf.metadata
            if metadata and "Title" in metadata:
                return metadata["Title"]
    except Exception:
        pass

    return ""
