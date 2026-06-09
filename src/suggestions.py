"""
搜索建议模块。

功能：
- 从搜索结果 HTML 中提取相关搜索词
- 查询改写（优化查询质量）
- 拼写纠错建议（从搜索引擎的 "did you mean" 提取）
"""

from __future__ import annotations

import re
from urllib.parse import urlparse, parse_qs, unquote


def extract_related_searches(html: str, engine: str = "") -> list[str]:
    """从搜索结果 HTML 中提取相关搜索词。

    支持 Google、Bing、DuckDuckGo、Brave 的 "related searches" 区域。
    """
    related = []

    if engine in ("google", ""):
        related.extend(_extract_google_related(html))
    if engine in ("bing", ""):
        related.extend(_extract_bing_related(html))
    if engine in ("brave", ""):
        related.extend(_extract_brave_related(html))
    if engine in ("duckduckgo", ""):
        related.extend(_extract_ddg_related(html))

    # 去重保序
    seen = set()
    unique = []
    for term in related:
        term = term.strip()
        if term and term.lower() not in seen:
            seen.add(term.lower())
            unique.append(term)

    return unique[:10]  # 最多 10 个


def extract_spell_correction(html: str, engine: str = "") -> str | None:
    """从搜索结果 HTML 中提取拼写纠错建议。

    返回搜索引擎建议的正确拼写，或 None。
    """
    if engine in ("google", ""):
        correction = _extract_google_correction(html)
        if correction:
            return correction

    if engine in ("bing", ""):
        correction = _extract_bing_correction(html)
        if correction:
            return correction

    return None


def rewrite_query(query: str) -> list[str]:
    """查询改写：生成优化后的查询变体。

    返回 0-3 个改写建议（不包括原始查询）。
    """
    suggestions = []
    query = query.strip()
    if not query:
        return suggestions

    # 1. 精确匹配：如果查询包含多个词且没有引号，添加引号版本
    if " " in query and '"' not in query and len(query.split()) <= 5:
        suggestions.append(f'"{query}"')

    # 2. 去除多余空格
    normalized = re.sub(r"\s+", " ", query)
    if normalized != query:
        suggestions.append(normalized)

    # 3. 如果查询太长，截取核心部分
    words = query.split()
    if len(words) > 8:
        # 保留前 6 个词
        shortened = " ".join(words[:6])
        suggestions.append(shortened)

    return suggestions[:3]


# ── Google 相关搜索提取 ────────────────────────────────────


def _extract_google_related(html: str) -> list[str]:
    """从 Google HTML 提取相关搜索。"""
    related = []

    # 方法 1: 相关搜索链接（div.related-question-pair 或 a 包含 "search?q="）
    # Google 相关搜索在 div 中包含 a[href*="/search?q="]
    import re as _re
    # 匹配 "相关搜索" 区域的链接
    matches = _re.findall(
        r'<a[^>]+href="/search\?q=([^"&]+)[^"]*"[^>]*>([^<]+)</a>',
        html,
        _re.IGNORECASE,
    )
    for encoded_query, text in matches[:10]:
        decoded = unquote(encoded_query).replace("+", " ")
        if decoded and len(decoded) > 2:
            related.append(decoded)

    # 方法 2: "People also ask" 或 "Related searches" 的 li 元素
    if not related:
        matches = _re.findall(
            r'class="[^"]*(?:related|suggestion)[^"]*"[^>]*>([^<]+)</(?:span|div|a)>',
            html,
            _re.IGNORECASE,
        )
        related.extend(matches[:10])

    return related


def _extract_google_correction(html: str) -> str | None:
    """从 Google HTML 提取拼写纠错。"""
    import re as _re
    # "Did you mean: <a>corrected</a>"
    match = _re.search(
        r'did you mean[^<]*<a[^>]*>([^<]+)</a>',
        html,
        _re.IGNORECASE,
    )
    if match:
        return match.group(1).strip()

    # "Showing results for <a>corrected</a>"
    match = _re.search(
        r'showing results for[^<]*<a[^>]*>([^<]+)</a>',
        html,
        _re.IGNORECASE,
    )
    if match:
        return match.group(1).strip()

    return None


# ── Bing 相关搜索提取 ─────────────────────────────────────


def _extract_bing_related(html: str) -> list[str]:
    """从 Bing HTML 提取相关搜索。"""
    import re as _re
    related = []

    # Bing 相关搜索在 div.b_rsbox 或 ul.b_vList 中
    matches = _re.findall(
        r'<a[^>]+href="[^"]*search\?q=([^"&]+)[^"]*"[^>]*class="[^"]*[^>]*>([^<]+)</a>',
        html,
        _re.IGNORECASE,
    )
    for encoded_query, text in matches[:10]:
        decoded = unquote(encoded_query).replace("+", " ")
        if decoded and len(decoded) > 2:
            related.append(decoded)

    # 备用：直接匹配 "Related searches" 区域
    if not related:
        matches = _re.findall(
            r'class="[^"]*related_search[^"]*"[^>]*>([^<]+)</(?:a|span)>',
            html,
            _re.IGNORECASE,
        )
        related.extend(matches[:10])

    return related


def _extract_bing_correction(html: str) -> str | None:
    """从 Bing HTML 提取拼写纠错。"""
    import re as _re
    match = _re.search(
        r'did you mean[^<]*<a[^>]*>([^<]+)</a>',
        html,
        _re.IGNORECASE,
    )
    if match:
        return match.group(1).strip()

    match = _re.search(
        r'showing results for[^<]*<a[^>]*>([^<]+)</a>',
        html,
        _re.IGNORECASE,
    )
    if match:
        return match.group(1).strip()

    return None


# ── Brave 相关搜索提取 ────────────────────────────────────


def _extract_brave_related(html: str) -> list[str]:
    """从 Brave HTML 提取相关搜索。"""
    import re as _re
    related = []

    # Brave 相关搜索在 "People also search for" 区域
    matches = _re.findall(
        r'class="[^"]*related-query[^"]*"[^>]*>([^<]+)</(?:a|span|div)>',
        html,
        _re.IGNORECASE,
    )
    related.extend(matches[:10])

    # 备用：搜索链接
    if not related:
        matches = _re.findall(
            r'<a[^>]+href="[^"]*search\?q=([^"&]+)[^"]*"[^>]*>([^<]+)</a>',
            html,
            _re.IGNORECASE,
        )
        for encoded_query, text in matches[:10]:
            decoded = unquote(encoded_query).replace("+", " ")
            if decoded and len(decoded) > 2:
                related.append(decoded)

    return related


# ── DuckDuckGo 相关搜索提取 ───────────────────────────────


def _extract_ddg_related(html: str) -> list[str]:
    """从 DuckDuckGo HTML 提取相关搜索。"""
    import re as _re
    related = []

    # DuckDuckGo 相关搜索在 "Related searches" 区域
    matches = _re.findall(
        r'class="[^"]*related[^"]*"[^>]*>([^<]+)</(?:a|span)>',
        html,
        _re.IGNORECASE,
    )
    related.extend(matches[:10])

    # 备用：匹配搜索链接
    if not related:
        matches = _re.findall(
            r'<a[^>]+href="[^"]*\?q=([^"&]+)[^"]*"[^>]*>([^<]+)</a>',
            html,
            _re.IGNORECASE,
        )
        for encoded_query, text in matches[:10]:
            decoded = unquote(encoded_query).replace("+", " ")
            if decoded and len(decoded) > 2:
                related.append(decoded)

    return related
