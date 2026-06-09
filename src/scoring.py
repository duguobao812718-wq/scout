"""
搜索结果评分模块。

多维度质量信号，叠加到 RRF 分数上：
- 域名信誉：白名单加分，黑名单减分
- 新鲜度：越新越高分
- 多引擎命中：被更多引擎发现的结果加分
- 页面质量：标题/摘要/URL 结构信号
"""

from __future__ import annotations

import re
from urllib.parse import urlparse


# ── 域名信誉 ──────────────────────────────────────────────

# 高质量域名白名单（加分）
_DOMAIN_WHITELIST: dict[str, float] = {
    # 官方文档
    "docs.python.org": 0.15,
    "developer.mozilla.org": 0.15,
    "learn.microsoft.com": 0.15,
    "docs.oracle.com": 0.12,
    "kotlinlang.org": 0.12,
    "rust-lang.org": 0.12,
    "go.dev": 0.12,
    # 知识库
    "wikipedia.org": 0.10,
    "stackoverflow.com": 0.10,
    "github.com": 0.08,
    "arxiv.org": 0.08,
    # 高质量媒体
    "nature.com": 0.12,
    "science.org": 0.12,
    "ieee.org": 0.10,
    "acm.org": 0.10,
    "scholar.google.com": 0.10,
    # 技术博客
    "medium.com": 0.03,
    "dev.to": 0.05,
    "hackernews.com": 0.05,
    "news.ycombinator.com": 0.05,
}

# 低质量域名黑名单（减分）
_DOMAIN_BLACKLIST: set[str] = {
    # 农场/聚合
    "pinterest.com",
    "quora.com",
    "answers.com",
    "wikihow.com",
    # SEO 垃圾
    "ehow.com",
    "techwalla.com",
    "azcentral.com",
}


def domain_reputation_score(url: str) -> float:
    """计算域名信誉分数 (-0.2 ~ +0.15)。"""
    try:
        host = urlparse(url).hostname or ""
    except Exception:
        return 0.0

    host = host.lower()
    if host.startswith("www."):
        host = host[4:]

    # 黑名单检查
    for blocked in _DOMAIN_BLACKLIST:
        if host == blocked or host.endswith("." + blocked):
            return -0.2

    # 白名单检查（支持子域名匹配）
    for trusted, score in _DOMAIN_WHITELIST.items():
        if host == trusted or host.endswith("." + trusted):
            return score

    return 0.0


# ── 新鲜度加权 ────────────────────────────────────────────


def freshness_score(published_age: str) -> float:
    """根据发布时间计算新鲜度分数 (0.0 ~ 0.1)。

    越新越高分：
    - 小时/分钟前：0.1
    - 天前：0.08
    - 周前：0.05
    - 月前：0.03
    - 年前：0.01
    - 无日期信息：0.0
    """
    if not published_age:
        return 0.0

    age = published_age.lower()

    # 分钟/小时前
    if re.search(r"\d+\s*(minute|hour|分钟|小时)", age):
        return 0.10

    # 天前
    if re.search(r"\d+\s*(day|天)", age):
        return 0.08

    # 周前
    if re.search(r"\d+\s*(week|周)", age):
        return 0.05

    # 月前
    if re.search(r"\d+\s*(month|月)", age):
        return 0.03

    # 年前
    if re.search(r"\d+\s*(year|年)", age):
        return 0.01

    # 绝对日期（解析后判断新旧）
    if re.search(r"\d{4}-\d{2}-\d{2}", age):
        # 简单启发：包含当前年份的加分
        from datetime import datetime
        current_year = str(datetime.now().year)
        if current_year in age:
            return 0.05
        return 0.02

    return 0.0


# ── 多引擎命中加权 ────────────────────────────────────────


def multi_engine_score(engine_count: int) -> float:
    """根据命中引擎数量计算分数 (0.0 ~ 0.15)。

    - 1 个引擎：0.0
    - 2 个引擎：0.08
    - 3+ 个引擎：0.15
    """
    if engine_count <= 1:
        return 0.0
    if engine_count == 2:
        return 0.08
    return 0.15


# ── 页面质量信号 ──────────────────────────────────────────


def page_quality_score(title: str, snippet: str, url: str) -> float:
    """计算页面质量信号分数 (0.0 ~ 0.1)。

    信号：
    - 标题长度（太短或太长都减分）
    - 摘要质量（有摘要加分）
    - URL 结构（干净的 URL 加分）
    """
    score = 0.0

    # 标题质量
    title_len = len(title.strip())
    if 10 <= title_len <= 100:
        score += 0.03  # 合理长度
    elif title_len < 5:
        score -= 0.02  # 太短

    # 摘要质量
    snippet_len = len(snippet.strip())
    if snippet_len > 50:
        score += 0.03  # 有实质性摘要
    elif snippet_len > 20:
        score += 0.01

    # URL 结构
    try:
        path = urlparse(url).path
        # 短路径通常更权威
        if path and path.count("/") <= 3:
            score += 0.02
        # 避免过长的 URL（可能是参数堆砌）
        if len(url) > 200:
            score -= 0.02
        # 有文件扩展名的可能是直接文档
        if re.search(r"\.(pdf|doc|docx|txt)$", path, re.IGNORECASE):
            score += 0.02
    except Exception:
        pass

    return max(0.0, min(0.1, score))


# ── 综合评分 ──────────────────────────────────────────────


def compute_quality_bonus(
    url: str,
    title: str,
    snippet: str,
    engine_count: int,
    published_age: str = "",
) -> float:
    """计算综合质量加分 (-0.2 ~ +0.5)。

    叠加到 RRF 分数上，影响最终排名。
    """
    bonus = 0.0
    bonus += domain_reputation_score(url)
    bonus += freshness_score(published_age)
    bonus += multi_engine_score(engine_count)
    bonus += page_quality_score(title, snippet, url)
    return bonus
