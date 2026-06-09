"""
Playwright 浏览器池。

用于抓取 JavaScript 渲染的页面。
参考：free-search-mcp 的 browser.py 实现。
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger("scout.browser")


class BrowserPool:
    """异步 Playwright 浏览器池。

    特性：
    - 懒初始化（首次使用时启动）
    - 可配置池大小
    - 自动超时和清理
    - 可选代理支持
    """

    def __init__(self) -> None:
        self._playwright = None
        self._browser = None
        self._initialized = False

    async def start(self, pool_size: int = 2) -> None:
        """启动浏览器池。"""
        if self._initialized:
            return

        try:
            from playwright.async_api import async_playwright

            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                ],
            )
            self._initialized = True
            logger.info("浏览器池已启动（池大小: %d）", pool_size)
        except ImportError:
            logger.warning("Playwright 未安装，浏览器功能不可用")
            raise
        except Exception as e:
            logger.error("浏览器池启动失败: %s", e)
            raise

    async def fetch_html(
        self,
        url: str,
        wait_selector: str | None = None,
        timeout: float = 30.0,
        proxy: str | None = None,
    ) -> str:
        """使用浏览器抓取页面 HTML。

        Args:
            url: 目标 URL。
            wait_selector: 等待特定元素出现的选择器。
            timeout: 超时秒数。
            proxy: 代理 URL。

        Returns:
            HTML 字符串。
        """
        if not self._initialized:
            await self.start()

        page = None
        try:
            # 创建新页面
            page = await self._browser.new_page(
                proxy={"server": proxy} if proxy else None,
            )

            # 设置 User-Agent
            await page.set_extra_http_headers({
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            })

            # 导航到页面
            response = await page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=timeout * 1000,
            )

            if response is None:
                raise ValueError(f"导航失败: {url}")

            # 等待特定元素
            if wait_selector:
                try:
                    await page.wait_for_selector(wait_selector, timeout=5000)
                except Exception:
                    logger.debug("等待选择器超时: %s", wait_selector)

            # 等待页面加载
            await asyncio.sleep(1)

            # 获取 HTML
            html = await page.content()

            if not html or not html.strip():
                raise ValueError(f"页面内容为空: {url}")

            return html

        except Exception as e:
            logger.warning("浏览器抓取失败 %s: %s", url, e)
            raise
        finally:
            if page:
                try:
                    await page.close()
                except Exception:
                    pass

    async def shutdown(self) -> None:
        """关闭浏览器池。"""
        if self._browser:
            try:
                await self._browser.close()
            except Exception:
                pass
            self._browser = None

        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception:
                pass
            self._playwright = None

        self._initialized = False
        logger.info("浏览器池已关闭")


# 全局浏览器池实例
pool = BrowserPool()
