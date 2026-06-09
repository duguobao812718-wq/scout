"""
Scout 搜索引擎抽象层。

核心设计（源自 free-search-mcp）：
  - Engine ABC：build_url() + parse() 为纯函数，无 I/O
  - search() 在基类中编排完整流程：fetch → parse → gate detection → post-filter
  - ENGINES 注册表：按名称查找引擎实例
"""

from __future__ import annotations

import abc
import logging
import re
import urllib.parse
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from bs4 import BeautifulSoup, Tag

from ..config import settings

logger = logging.getLogger("scout.engines")


# ── 数据结构 ──────────────────────────────────────────────


@dataclass(slots=True)
class SearchFilters:
    """搜索过滤条件，适用于所有引擎。"""

    freshness: Literal["day", "week", "month", "year"] | None = None
    include_domains: list[str] = field(default_factory=list)
    exclude_domains: list[str] = field(default_factory=list)
    category: Literal["news", "pdf", "github", "paper", "forum", "blog"] | None = None
    include_text: str | None = None
    exclude_text: str | None = None


@dataclass(slots=True)
class SearchResult:
    """单条搜索结果。"""

    title: str
    url: str
    snippet: str
    engine: str
    rank: int = 0
    published_age: str = ""  # "2 days ago", "3 hours ago" 等


# ── 引擎 ABC ──────────────────────────────────────────────


class Engine(abc.ABC):
    """搜索引擎抽象基类。

    子类必须实现：
      - build_url(): 构建搜索 URL（纯函数）
      - parse(): 解析 HTML 为结果列表（纯函数）

    基类提供：
      - search(): 完整搜索流程（fetch → parse → gate detection → post-filter）
    """

    name: str = ""
    needs_browser: bool = False
    supports_freshness: bool = True
    supports_safesearch: bool = True

    @abc.abstractmethod
    def build_url(
        self,
        query: str,
        max_results: int,
        filters: SearchFilters | None = None,
    ) -> str:
        """构建搜索引擎 URL。纯函数，无 I/O。"""
        ...

    @abc.abstractmethod
    def parse(self, html: str) -> list[SearchResult]:
        """解析 HTML 为搜索结果列表。纯函数，无 I/O。"""
        ...

    async def search(
        self,
        query: str,
        max_results: int = 10,
        filters: SearchFilters | None = None,
        diagnostics: dict[str, Any] | None = None,
        max_retries: int = 2,
    ) -> list[SearchResult]:
        """完整搜索流程。

        1. build_url() 构建 URL
        2. _fetch() 获取 HTML（带重试）
        3. detect_gate() 检测封锁
        4. parse() 解析结果
        5. apply_post_filters() 后过滤
        6. 设置 rank
        """
        filters = filters or SearchFilters()
        diag = diagnostics or {}

        url = self.build_url(query, max_results, filters)
        diag.setdefault(self.name, {})["url"] = url

        # 带重试的抓取
        html = None
        for attempt in range(max_retries + 1):
            try:
                html = await self._fetch(url)
                break
            except Exception as e:
                if attempt < max_retries:
                    logger.warning("引擎 %s 抓取失败 (尝试 %d/%d): %s", self.name, attempt + 1, max_retries + 1, e)
                    import asyncio
                    await asyncio.sleep(1.0 * (attempt + 1))
                else:
                    diag[self.name]["error"] = str(e)
                    logger.warning("引擎 %s 抓取失败: %s", self.name, e)
                    return []

        if html is None:
            return []

        # 门控检测
        gate = detect_gate(html)
        if gate:
            diag[self.name]["gate"] = gate
            logger.warning("引擎 %s 触发门控: %s", self.name, gate)
            return []

        # 解析
        try:
            results = self.parse(html)
        except Exception as e:
            diag[self.name]["parse_error"] = str(e)
            logger.warning("引擎 %s 解析失败: %s", self.name, e)
            return []

        # 后过滤
        results = apply_post_filters(results, filters)

        # 设置 rank
        for i, r in enumerate(results):
            r.rank = i + 1
            r.engine = self.name

        diag[self.name]["count"] = len(results)
        return results[:max_results]

    async def _fetch(self, url: str) -> str:
        """抓取 URL 内容。子类可覆盖以实现特殊抓取逻辑。"""
        from ..fetchers.http import fetch_html

        return await fetch_html(url, engine=self.name)


# ── 辅助函数 ──────────────────────────────────────────────


def parse_html(html: str) -> BeautifulSoup:
    """解析 HTML，使用 lxml 后端。"""
    return BeautifulSoup(html, "lxml")


def text_of(node: Tag | None) -> str:
    """安全提取节点文本，去除首尾空白。"""
    if node is None:
        return ""
    return node.get_text(strip=True)


def extract_date_hint(text: str) -> str:
    """从文本中提取日期提示（如 "2 days ago", "3 hours ago"）。"""
    if not text:
        return ""

    # 相对时间模式
    patterns = [
        r"(\d+)\s*(second|minute|hour|day|week|month|year)s?\s*ago",
        r"(\d+)\s*(秒|分钟|小时|天|周|月|年)\s*前",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(0)

    # 绝对日期模式
    date_patterns = [
        r"\b\d{4}-\d{2}-\d{2}\b",
        r"\b\d{2}/\d{2}/\d{4}\b",
        r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},?\s+\d{4}\b",
    ]
    for pattern in date_patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(0)

    return ""


def detect_gate(html: str) -> str | None:
    """检测 HTML 中的门控（CAPTCHA/consent/login）。

    返回门控类型，或 None（无门控）。
    使用更精确的检测，避免误报。
    """
    lower = html.lower()

    # CAPTCHA - 检测实际的 CAPTCHA 挑战页面
    # DuckDuckGo 特定的 CAPTCHA
    if "anomaly-modal" in html and "challenge" in lower:
        return "captcha"

    # 通用 CAPTCHA 挑战指示器
    captcha_patterns = [
        "are you a robot",
        "prove you are human",
        "verify you are human",
        "complete the following challenge",
        "solve the captcha",
        "select all squares containing",
        "unfortunately, bots use",
    ]
    for pattern in captcha_patterns:
        if pattern in lower:
            return "captcha"

    # reCAPTCHA/hCAPTCHA 的实际挑战容器（不是脚本引用）
    if ('class="g-recaptcha"' in html and 'data-sitekey' in html):
        return "captcha"
    if ('class="h-captcha"' in html and 'data-sitekey' in html):
        return "captcha"

    # Consent（GDPR 等）- 只检测实际的 consent 弹窗
    consent_patterns = [
        "accept all cookies",
        "accept cookies and continue",
        "we use cookies",
        "cookie consent",
        "gdpr consent",
    ]
    for pattern in consent_patterns:
        if pattern in lower:
            return "consent"

    # Login wall - 只检测明确的登录墙
    login_patterns = [
        "sign in to continue",
        "login to view this content",
        "subscribe to read",
        "create an account to continue",
    ]
    for pattern in login_patterns:
        if pattern in lower:
            return "login"

    return None


def apply_post_filters(
    results: list[SearchResult],
    filters: SearchFilters,
) -> list[SearchResult]:
    """客户端后过滤（引擎可能不完全遵守过滤条件）。"""
    if not filters.include_domains and not filters.exclude_domains:
        if not filters.include_text and not filters.exclude_text:
            return results

    filtered = []
    for r in results:
        # 域名过滤
        if filters.include_domains:
            host = urllib.parse.urlparse(r.url).hostname or ""
            if not any(d in host for d in filters.include_domains):
                continue

        if filters.exclude_domains:
            host = urllib.parse.urlparse(r.url).hostname or ""
            if any(d in host for d in filters.exclude_domains):
                continue

        # 文本过滤
        text = f"{r.title} {r.snippet}".lower()

        if filters.include_text:
            if filters.include_text.lower() not in text:
                continue

        if filters.exclude_text:
            if filters.exclude_text.lower() in text:
                continue

        filtered.append(r)

    return filtered


def safesearch_value(engine_name: str) -> str | int | None:
    """根据引擎名称返回 safesearch 参数值。"""
    mapping = {
        "duckduckgo": {"strict": "1", "moderate": "-1", "off": "-2"},
        "bing": {"strict": "strict", "moderate": "moderate", "off": "off"},
        "brave": {"strict": "strict", "moderate": "moderate", "off": "off"},
        "google": {"strict": "1", "moderate": "", "off": ""},
    }
    engine_map = mapping.get(engine_name, {})
    return engine_map.get(settings.safesearch)


def freshness_value(
    engine_name: str,
    freshness: str | None,
) -> str | None:
    """根据引擎名称返回 freshness 参数值。"""
    if not freshness:
        return None

    mapping = {
        "duckduckgo": {"day": "d", "week": "w", "month": "m", "year": "y"},
        "bing": {"day": "ex1:ez1", "week": "ex1:ez2", "month": "ex1:ez3", "year": "ex1:ez4"},
        "brave": {"day": "pd", "week": "pw", "month": "pm", "year": "py"},
        "google": {"day": "qdr:d", "week": "qdr:w", "month": "qdr:m", "year": "qdr:y"},
    }
    engine_map = mapping.get(engine_name, {})
    return engine_map.get(freshness)


# ── 引擎注册表 ────────────────────────────────────────────

ENGINES: dict[str, Engine] = {}


def register_engine(engine: Engine) -> None:
    """注册引擎到全局注册表。"""
    ENGINES[engine.name] = engine


def get_engine(name: str) -> Engine:
    """按名称获取引擎，不存在则抛出异常。"""
    engine = ENGINES.get(name)
    if engine is None:
        available = ", ".join(sorted(ENGINES.keys())) or "(无)"
        raise ValueError(f"未知引擎: {name!r}。可用引擎: {available}")
    return engine


def list_engines() -> list[str]:
    """列出所有已注册的引擎名称。"""
    return sorted(ENGINES.keys())


# ── 延迟注册引擎 ──────────────────────────────────────────

def _register_builtin_engines() -> None:
    """注册内置引擎（延迟导入避免循环依赖）。"""
    from . import duckduckgo, bing, brave, google  # noqa: F401

    # 引擎在各自的模块中通过 register_engine() 自注册


# 模块加载时注册
_register_builtin_engines()
