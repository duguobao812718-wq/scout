"""
Markdown/JSON 格式化器。

LLM 友好的输出格式，参考 free-search-mcp 的 formatting.py。
"""

from __future__ import annotations

import re
from typing import Any


def estimate_tokens(text: str) -> int:
    """估算 token 数量（CJK 感知）。

    规则：
    - CJK 字符：1 字符 ≈ 1 token
    - 拉丁字符：4 字符 ≈ 1 token
    """
    if not text:
        return 0

    cjk_count = 0
    latin_count = 0

    for ch in text:
        if _is_cjk(ch):
            cjk_count += 1
        elif ch.isascii() and not ch.isspace():
            latin_count += 1

    return cjk_count + (latin_count + 3) // 4


def _is_cjk(ch: str) -> bool:
    """判断是否为 CJK 字符。"""
    cp = ord(ch)
    return (
        (0x4E00 <= cp <= 0x9FFF)    # CJK 统一汉字
        or (0x3400 <= cp <= 0x4DBF)  # CJK 扩展 A
        or (0xF900 <= cp <= 0xFAFF)  # CJK 兼容汉字
        or (0x3000 <= cp <= 0x303F)  # CJK 标点
        or (0xFF00 <= cp <= 0xFFEF)  # 全角字符
    )


def smart_truncate(text: str, max_chars: int) -> str:
    """智能截断，在自然边界处断开。

    优先级：段落 > 换行 > 句子 > 空格。
    最少保留 30% 的 max_chars。
    """
    if not text or len(text) <= max_chars:
        return text

    min_chars = int(max_chars * 0.3)
    truncated = text[:max_chars]

    # 尝试在段落边界断开
    last_para = truncated.rfind("\n\n")
    if last_para >= min_chars:
        return truncated[:last_para].rstrip()

    # 尝试在换行断开
    last_newline = truncated.rfind("\n")
    if last_newline >= min_chars:
        return truncated[:last_newline].rstrip()

    # 尝试在句子边界断开
    for sep in ["。", ".", "!", "?", "！", "？"]:
        last_sentence = truncated.rfind(sep)
        if last_sentence >= min_chars:
            return truncated[: last_sentence + 1].rstrip()

    # 尝试在空格断开
    last_space = truncated.rfind(" ")
    if last_space >= min_chars:
        return truncated[:last_space].rstrip()

    return truncated.rstrip()


def render_search(payload: dict[str, Any]) -> str:
    """渲染搜索结果为 Markdown。

    格式：
    1. title
    <url>
    snippet (engines: ...)
    """
    results = payload.get("results", [])
    if not results:
        hint = payload.get("hint", "")
        if hint:
            return f"_未找到结果。{hint}_\n"
        return "_未找到结果。_\n"

    lines = []
    for i, r in enumerate(results, 1):
        title = r.get("title", "(无标题)")
        url = r.get("url", "")
        snippet = r.get("snippet", "")
        engines = r.get("engines", [])
        score = r.get("score", 0)

        lines.append(f"{i}. **{title}**")
        lines.append(f"   <{url}>")
        if snippet:
            lines.append(f"   {snippet}")
        if engines:
            engine_str = ", ".join(engines)
            lines.append(f"   _来源: {engine_str} | 分数: {score:.2f}_")
        lines.append("")

    # 添加元信息
    meta_parts = []
    if "engines" in payload:
        meta_parts.append(f"引擎: {', '.join(payload['engines'])}")
    if "cached" in payload:
        meta_parts.append("缓存: 是" if payload["cached"] else "缓存: 否")
    if meta_parts:
        lines.append(f"---\n_{' | '.join(meta_parts)}_")

    return "\n".join(lines)


def render_fetch(result: dict[str, Any]) -> str:
    """渲染抓取结果为 Markdown。"""
    url = result.get("url", "")
    title = result.get("title", "(无标题)")
    content = result.get("content", "")
    method = result.get("method", "http")
    truncated = result.get("truncated", False)
    tokens = result.get("tokens_estimated", 0)

    lines = [
        f"# {title}",
        f"",
        f"> URL: <{url}>",
        f"> 方法: {method} | Token: ~{tokens}{' | ⚠ 已截断' if truncated else ''}",
        f"",
        content,
    ]

    return "\n".join(lines)


def render_research(payload: dict[str, Any]) -> str:
    """渲染研究结果为 Markdown。"""
    question = payload.get("question", "")
    sources = payload.get("sources", [])
    documents = payload.get("documents", [])
    tokens = payload.get("tokens_estimated", 0)

    lines = [
        f"# 研究报告",
        f"",
        f"> 问题: {question}",
        f"> 来源数: {len(sources)} | Token: ~{tokens}",
        f"",
    ]

    # 来源索引
    if sources:
        lines.append("## 来源\n")
        for i, s in enumerate(sources, 1):
            title = s.get("title", "(无标题)")
            url = s.get("url", "")
            lines.append(f"[{i}] **{title}**")
            lines.append(f"    <{url}>")
        lines.append("")

    # 文档内容
    if documents:
        lines.append("## 文档内容\n")
        for doc in documents:
            lines.append(render_fetch(doc))
            lines.append("\n---\n")

    return "\n".join(lines)


def errors_to_hint(errors: dict[str, Any] | None) -> str:
    """将引擎错误转换为 LLM 可理解的提示。"""
    if not errors:
        return ""

    hints = []
    for engine, error in errors.items():
        if isinstance(error, str):
            hints.append(f"- {engine}: {error}")
        elif isinstance(error, dict):
            msg = error.get("error", str(error))
            hints.append(f"- {engine}: {msg}")

    if not hints:
        return ""

    return "部分引擎出错:\n" + "\n".join(hints)


def render_structured(payload: dict[str, Any]) -> str:
    """渲染结构化数据为 Markdown。"""
    import json

    url = payload.get("url", "")
    lines = [f"# 结构化数据: {url}", ""]

    # JSON-LD
    json_ld = payload.get("json_ld", [])
    if json_ld:
        lines.append("## JSON-LD")
        lines.append("")
        for item in json_ld:
            lines.append("```json")
            lines.append(json.dumps(item, ensure_ascii=False, indent=2))
            lines.append("```")
            lines.append("")

    # OpenGraph
    og = payload.get("opengraph", {})
    if og:
        lines.append("## OpenGraph")
        lines.append("")
        for key, value in og.items():
            lines.append(f"- **{key}**: {value}")
        lines.append("")

    # Twitter Card
    twitter = payload.get("twitter_card", {})
    if twitter:
        lines.append("## Twitter Card")
        lines.append("")
        for key, value in twitter.items():
            lines.append(f"- **{key}**: {value}")
        lines.append("")

    # Microdata
    microdata = payload.get("microdata", [])
    if microdata:
        lines.append("## Microdata")
        lines.append("")
        for item in microdata:
            lines.append(f"### {item.get('type', 'Unknown')}")
            for key, value in item.get("properties", {}).items():
                lines.append(f"- **{key}**: {value}")
            lines.append("")

    if not (json_ld or og or twitter or microdata):
        lines.append("_未找到结构化数据_")

    return "\n".join(lines)
